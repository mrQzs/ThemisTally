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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from .authorization import (ApprovalLedger, ApprovalHead, AuthorizationError, InputLock,
                            canonical_bytes, validate_approval, validate_authorization)
from . import protocols


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

    @staticmethod
    def _journal_text(value: Any, field: str, line: int) -> str:
        if type(value) is not str or not value or len(value) > 256:
            raise AuthorizationStoreError("E_AUTH_JOURNAL", "/journal", f"invalid {field} at line {line}")
        if any(ord(ch) < 0x20 or 0x7F <= ord(ch) <= 0x9F or 0xD800 <= ord(ch) <= 0xDFFF
               for ch in value):
            raise AuthorizationStoreError("E_AUTH_JOURNAL", "/journal", f"invalid {field} at line {line}")
        return value

    def _validate_event_fields(self, event: Mapping[str, Any], line: int) -> None:
        """Keep malformed JSON values inside the journal error boundary.

        A JSON object can contain arrays/objects where the ledger expects a
        hashable identity.  Validating those fields before inserting into the
        operation sets prevents raw ``TypeError`` escapes during recovery.
        """
        self._journal_text(event.get("type"), "type", line)
        self._journal_text(event.get("scope"), "scope", line)
        self._journal_text(event.get("operation_id"), "operation_id", line)
        if event["type"] == "approval":
            generation = event.get("expected_generation")
            if type(generation) is not int or generation < 0:
                self._fail("E_AUTH_JOURNAL", f"invalid expected_generation at line {line}")
        elif event["type"] == "lock":
            self._journal_text(event.get("receipt_id"), "receipt_id", line)
            if not isinstance(event.get("bindings"), list):
                self._fail("E_AUTH_JOURNAL", f"invalid bindings at line {line}")
        else:
            generation = event.get("expected_generation")
            if type(generation) is not int or generation < 1:
                self._fail("E_AUTH_JOURNAL", f"invalid expected_generation at line {line}")
            self._journal_text(event.get("action"), "action", line)
            if not isinstance(event.get("input_refs"), list):
                self._fail("E_AUTH_JOURNAL", f"invalid input_refs at line {line}")
            consumed_at = event.get("consumed_at")
            self._journal_text(consumed_at, "consumed_at", line)

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
                # Journal replay must use the same strict bounded JSON profile
                # as new ledger writes.  ``json.loads`` would silently accept
                # duplicate keys, non-finite numbers, over-deep values and
                # records larger than the protocol byte limit.
                event = protocols.strict_json_loads(line)
            except (UnicodeDecodeError, json.JSONDecodeError, protocols.ProtocolError):
                if index == len(lines) - 1 and not complete:
                    self.recovery = {"status": "TRUNCATED_TAIL", "ignored_tail": True, "line": index + 1}
                    break
                self._fail("E_AUTH_JOURNAL", f"invalid non-tail event at line {index + 1}")
            if not complete and index == len(lines) - 1:
                self.recovery = {"status": "TRUNCATED_TAIL", "ignored_tail": True, "line": index + 1}
                break
            if not isinstance(event, dict):
                self._fail("E_AUTH_JOURNAL", f"event must be an object at line {index + 1}")
            event_type = self._journal_text(event.get("type"), "type", index + 1)
            approval_shape = {"seq", "type", "scope", "operation_id", "expected_generation", "record"}
            lock_shape = {"seq", "type", "scope", "operation_id", "receipt_id", "bindings"}
            consume_shape = {"seq", "type", "scope", "operation_id", "expected_generation", "action", "input_refs", "consumed_at"}
            if event_type == "approval" and set(event) != approval_shape:
                self._fail("E_AUTH_JOURNAL", f"invalid approval shape at line {index + 1}")
            if event_type == "lock" and set(event) != lock_shape:
                self._fail("E_AUTH_JOURNAL", f"invalid lock shape at line {index + 1}")
            if event_type == "consume" and set(event) != consume_shape:
                self._fail("E_AUTH_JOURNAL", f"invalid consume shape at line {index + 1}")
            if event_type not in {"approval", "lock", "consume"}:
                self._fail("E_AUTH_JOURNAL", f"unknown event type at line {index + 1}")
            self._validate_event_fields(event, index + 1)
            seq = event.get("seq")
            if type(seq) is not int or seq != self.high_water + 1:
                self._fail("E_AUTH_JOURNAL", f"non-contiguous sequence at line {index + 1}")
            operation_key = (event["type"], event["operation_id"])
            if operation_key in self._operation_events:
                self._fail("E_AUTH_JOURNAL", f"duplicate operation event at line {index + 1}")
            self.high_water = seq
            if event["type"] == "approval":
                try:
                    self.ledger.put(scope=event["scope"], operation_id=event["operation_id"], expected_generation=event["expected_generation"], record=event["record"])
                except (AuthorizationError, TypeError, KeyError, ValueError) as exc:
                    self._fail("E_AUTH_JOURNAL", f"invalid approval at line {index + 1}: {exc}")
            elif event["type"] == "lock":
                try:
                    self.ledger.lock(scope=event["scope"], receipt_id=event["receipt_id"], operation_id=event["operation_id"], bindings=event["bindings"])
                except (AuthorizationError, TypeError, KeyError, ValueError) as exc:
                    self._fail("E_AUTH_JOURNAL", f"invalid lock at line {index + 1}: {exc}")
            elif event["type"] == "consume":
                try:
                    consumed_at = datetime.fromisoformat(event["consumed_at"].replace("Z", "+00:00"))
                except (AttributeError, TypeError, ValueError):
                    self._fail("E_AUTH_JOURNAL", f"invalid consumed_at at line {index + 1}")
                if consumed_at.tzinfo is None or consumed_at.utcoffset() is None:
                    self._fail("E_AUTH_JOURNAL", f"consumed_at must include timezone at line {index + 1}")
                try:
                    if not self.ledger.consume_once(scope=event["scope"], action=event["action"],
                                                    input_refs=event["input_refs"], operation_id=event["operation_id"],
                                                    expected_generation=event["expected_generation"], now=consumed_at):
                        self._fail("E_AUTH_JOURNAL", f"consume event was not applicable at line {index + 1}")
                except (AuthorizationError, TypeError, KeyError, ValueError) as exc:
                    self._fail("E_AUTH_JOURNAL", f"invalid consume at line {index + 1}: {exc}")
            self._operation_events.add(operation_key)

    def _append(self, event: Mapping[str, Any]) -> None:
        # Apply the same line-oriented boundary to new events that replay uses
        # for existing journal bytes.  Build the candidate ledger first; a
        # rejected event therefore cannot publish in-memory state.
        self._validate_event_fields(event, self.high_water + 1)
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

    def _commit(self, candidate: ApprovalLedger, event: Mapping[str, Any]) -> None:
        """Publish in-memory state only after its append has been durable.

        An append/fsync error has an unknown disk outcome.  Retain the last
        durable in-memory state and fence further writes until the journal is
        reopened and reconciled; a retry must not silently use a ghost head.
        """
        try:
            self._append(event)
        except OSError as exc:
            self.recovery = {"status": "WRITE_UNKNOWN", "ignored_tail": False}
            raise AuthorizationStoreError("E_AUTH_WRITE_UNKNOWN", "/journal", "journal append outcome is unknown") from exc
        self.ledger = candidate
        self._operation_events.add((event["type"], event["operation_id"]))

    def put(self, *, scope: str, operation_id: str, expected_generation: int, record: Mapping[str, Any]) -> ApprovalHead:
        self._ensure_writable()
        normalized = validate_approval(record)
        candidate = copy.deepcopy(self.ledger)
        head = candidate.put(scope=scope, operation_id=operation_id, expected_generation=expected_generation, record=normalized)
        replay = ("approval", operation_id) in self._operation_events
        if replay:
            return head
        self._commit(candidate, {"seq": self.high_water + 1, "type": "approval", "scope": scope, "operation_id": operation_id,
                                 "expected_generation": expected_generation, "record": normalized})
        return head

    def put_authorization(self, *, scope: str, operation_id: str, expected_generation: int,
                          record: Mapping[str, Any]) -> ApprovalHead:
        validate_authorization(record)
        return self.put(scope=scope, operation_id=operation_id,
                        expected_generation=expected_generation, record=record)

    def lock(self, *, scope: str, receipt_id: str, operation_id: str, bindings: list[Mapping[str, Any]]) -> InputLock:
        self._ensure_writable()
        try:
            binding_list = copy.deepcopy(list(bindings))
        except TypeError as exc:
            self._fail("E_LOCK_BINDINGS", "bindings must be iterable")
        candidate = copy.deepcopy(self.ledger)
        lock = candidate.lock(scope=scope, receipt_id=receipt_id, operation_id=operation_id, bindings=binding_list)
        replay = ("lock", operation_id) in self._operation_events
        if replay:
            return lock
        self._commit(candidate, {"seq": self.high_water + 1, "type": "lock", "scope": scope, "operation_id": operation_id,
                                 "receipt_id": receipt_id, "bindings": binding_list})
        return lock

    def consume_once(self, *, scope: str, action: str, input_refs: list[Mapping[str, Any]],
                     operation_id: str, expected_generation: int,
                     now: Any = None) -> bool:
        self._ensure_writable()
        effective_now = datetime.now(timezone.utc) if now is None else now
        if not isinstance(effective_now, datetime) or effective_now.tzinfo is None or effective_now.utcoffset() is None:
            self._fail("E_AUTHORIZATION_TIME", "consume time must include timezone")
        try:
            input_refs_list = copy.deepcopy(list(input_refs))
        except TypeError:
            self._fail("E_CONSUME_BINDING", "input_refs must be iterable")
        candidate = copy.deepcopy(self.ledger)
        result = candidate.consume_once(scope=scope, action=action, input_refs=input_refs_list,
                                         operation_id=operation_id, expected_generation=expected_generation,
                                         now=effective_now)
        replay = ("consume", operation_id) in self._operation_events
        if not result or replay:
            return result
        consumed_at = effective_now
        self._commit(candidate, {"seq": self.high_water + 1, "type": "consume", "scope": scope,
                                 "operation_id": operation_id, "expected_generation": expected_generation,
                      "action": action, "input_refs": input_refs_list,
                                 "consumed_at": consumed_at.isoformat().replace("+00:00", "Z")})
        return True

    def _has_lock_receipt(self, receipt_id: str) -> bool:
        # The in-memory ledger intentionally exposes no mutable receipt map; a
        # replay can be recognized by scanning the journal's immutable events.
        if not self.path.exists():
            return False
        for line in self.path.read_bytes().splitlines():
            try:
                event = protocols.strict_json_loads(line)
            except (UnicodeDecodeError, json.JSONDecodeError, protocols.ProtocolError):
                continue
            if isinstance(event, dict) and event.get("type") == "lock" and event.get("receipt_id") == receipt_id:
                return True
        return False

    def reconcile(self) -> Dict[str, Any]:
        return {"high_water": self.high_water, "recovery": copy.deepcopy(self.recovery), "scopes": sorted(self.ledger._heads)}


__all__ = ["AuthorizationStoreError", "PersistentApprovalStore"]
