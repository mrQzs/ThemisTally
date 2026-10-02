"""Offline approval, authorization and input-lock ledger primitives.

The ledger is deliberately in-memory and deterministic.  Production callers
must persist the immutable records and re-check the 03/05/07 gates before any
side effect; this module never starts a process or grants a permission by
itself.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import ntpath
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple


HEX64 = re.compile(r"^[0-9a-f]{64}$")
DECISIONS = {"APPROVED", "REJECTED", "REVOKED", "UNKNOWN"}


class AuthorizationError(ValueError):
    def __init__(self, code: str, path: str, message: str):
        self.code, self.path = code, path
        super().__init__(f"{code} at {path}: {message}")


def _fail(code: str, path: str, message: str) -> None:
    raise AuthorizationError(code, path, message)


def canonical_bytes(value: Any) -> bytes:
    try:
        return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise AuthorizationError("E_JSON_NUMBER", "/", str(exc)) from exc


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value) if not isinstance(value, bytes) else value).hexdigest()


def _ref(value: Any, path: str) -> Dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"kind", "id", "path", "sha256"}:
        _fail("E_RESOURCE_FIELD", path, "ResourceRef must be closed")
    for key in ("kind", "id", "path"):
        if not isinstance(value[key], str) or not value[key]:
            _fail("E_RESOURCE_FIELD", f"{path}/{key}", "non-empty string required")
    if not isinstance(value["sha256"], str) or not HEX64.fullmatch(value["sha256"]):
        _fail("E_RESOURCE_HASH", f"{path}/sha256", "lowercase SHA-256 required")
    normalized = value["path"].replace("\\", "/")
    if (normalized.startswith("/") or ntpath.splitdrive(normalized)[0] or any(part in {"", ".", ".."} for part in normalized.split("/")) or any(ord(ch) < 32 for ch in normalized)):
        _fail("E_RESOURCE_PATH", f"{path}/path", "path traversal is forbidden")
    result = copy.deepcopy(value); result["path"] = normalized
    return result


def validate_approval(record: Mapping[str, Any]) -> Dict[str, Any]:
    required = {"record_type", "schema_version", "approval_id", "request_id", "subject_ref", "input_refs",
                "reviewed_actions", "decision", "recorded_at", "reviewer"}
    allowed = required | {"authorization_refs", "conditions", "expires_at", "not_before", "purpose", "rationale", "supersedes"}
    if not isinstance(record, dict):
        _fail("E_APPROVAL_SCHEMA", "/", "approval must be an object")
    unknown = set(record) - allowed
    if unknown:
        _fail("E_APPROVAL_UNKNOWN_FIELD", "/", f"unknown fields: {sorted(unknown)}")
    missing = required - set(record)
    if missing:
        _fail("E_APPROVAL_SCHEMA", "/", f"missing fields: {sorted(missing)}")
    if record["record_type"] != "approval-record" or record["schema_version"] != 1:
        _fail("E_APPROVAL_VERSION", "/record_type", "approval-record schema version 1 required")
    for key in ("approval_id", "request_id"):
        if not isinstance(record[key], str) or not record[key]:
            _fail("E_APPROVAL_SCHEMA", f"/{key}", "non-empty string required")
    _ref(record["subject_ref"], "/subject_ref")
    for timestamp in ("recorded_at", "not_before", "expires_at"):
        if timestamp in record and record[timestamp] is not None:
            if not isinstance(record[timestamp], str): _fail("E_APPROVAL_TIME", f"/{timestamp}", "ISO-8601 timestamp required")
            try:
                parsed = datetime.fromisoformat(record[timestamp].replace("Z", "+00:00"))
            except ValueError:
                _fail("E_APPROVAL_TIME", f"/{timestamp}", "invalid ISO-8601 timestamp")
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                _fail("E_APPROVAL_TIME", f"/{timestamp}", "timezone offset required")
    if record.get("not_before") and record.get("expires_at") and datetime.fromisoformat(record["not_before"].replace("Z", "+00:00")) >= datetime.fromisoformat(record["expires_at"].replace("Z", "+00:00")):
        _fail("E_APPROVAL_TIME", "/expires_at", "expiry must follow not_before")
    if not isinstance(record["input_refs"], list) or len({json.dumps(x, sort_keys=True) for x in record["input_refs"]}) != len(record["input_refs"]):
        _fail("E_APPROVAL_SCHEMA", "/input_refs", "unique ResourceRef array required")
    for i, value in enumerate(record["input_refs"]):
        _ref(value, f"/input_refs/{i}")
    if not isinstance(record["reviewed_actions"], list) or not record["reviewed_actions"] or any(not isinstance(x, str) or not x for x in record["reviewed_actions"]):
        _fail("E_APPROVAL_SCHEMA", "/reviewed_actions", "non-empty action array required")
    if record["decision"] not in DECISIONS:
        _fail("E_APPROVAL_SCHEMA", "/decision", "unknown approval decision")
    if not isinstance(record["reviewer"], dict) or not isinstance(record["reviewer"].get("mode"), str):
        _fail("E_APPROVAL_SCHEMA", "/reviewer", "reviewer mode required")
    for name in ("authorization_refs",):
        if name in record:
            if not isinstance(record[name], list):
                _fail("E_APPROVAL_SCHEMA", f"/{name}", "array required")
            for i, value in enumerate(record[name]):
                _ref(value, f"/{name}/{i}")
    return copy.deepcopy(dict(record))


def validate_authorization(record: Mapping[str, Any]) -> Dict[str, Any]:
    """Validate the stricter v2 authorization envelope.

    ``validate_approval`` remains the compatibility parser for legacy records;
    this entry point is used when a new authorization is being issued and
    requires the explicit purpose, evidence references, conditions and reason
    fields from the 03 contract.
    """
    normalized = validate_approval(record)
    required = {"purpose", "authorization_refs", "conditions", "rationale"}
    missing = sorted(required - set(normalized))
    if missing:
        _fail("E_AUTHORIZATION_SCHEMA", "/", f"missing fields: {missing}")
    if type(normalized["purpose"]) is not str or not normalized["purpose"].strip():
        _fail("E_AUTHORIZATION_SCHEMA", "/purpose", "non-empty purpose required")
    refs = normalized["authorization_refs"]
    if not isinstance(refs, list) or not refs:
        _fail("E_AUTHORIZATION_SCHEMA", "/authorization_refs", "non-empty ResourceRef array required")
    for index, value in enumerate(refs):
        _ref(value, f"/authorization_refs/{index}")
    if not isinstance(normalized["conditions"], dict):
        _fail("E_AUTHORIZATION_SCHEMA", "/conditions", "conditions object required")
    if type(normalized["rationale"]) is not str or not normalized["rationale"].strip():
        _fail("E_AUTHORIZATION_SCHEMA", "/rationale", "non-empty rationale required")
    return normalized


@dataclass(frozen=True)
class ApprovalHead:
    scope: str
    generation: int
    record: Dict[str, Any]
    record_sha256: str


@dataclass(frozen=True)
class InputLock:
    receipt_id: str
    approval_ref: Dict[str, Any]
    bindings: Tuple[Tuple[Dict[str, Any], int], ...]
    head_generation: int
    receipt_sha256: str


class ApprovalLedger:
    """Append-only approval heads with CAS and idempotent operation keys."""

    def __init__(self) -> None:
        self._heads: Dict[str, ApprovalHead] = {}
        self._history: Dict[str, list[ApprovalHead]] = {}
        self._operations: Dict[str, Tuple[str, int, str, ApprovalHead]] = {}
        self._lock_operations: Dict[str, Tuple[str, str, str, InputLock]] = {}
        self._receipts: Dict[str, InputLock] = {}
        self._revoke_operations: Dict[str, Tuple[str, int, str, ApprovalHead]] = {}
        self._consumptions: Dict[str, Tuple[str, str, str, int]] = {}
        self._consumed_keys: Dict[Tuple[str, str, str, int], str] = {}

    def put(self, *, scope: str, operation_id: str, expected_generation: int, record: Mapping[str, Any]) -> ApprovalHead:
        if not scope or not operation_id:
            _fail("E_APPROVAL_SCHEMA", "/", "scope and operation_id are required")
        normalized = validate_approval(record)
        request_hash = sha256(normalized)
        if operation_id in self._operations:
            old_scope, old_generation, old_hash, old_head = self._operations[operation_id]
            if old_scope != scope or old_generation != expected_generation or old_hash != request_hash:
                _fail("E_IDEMPOTENCY_CONFLICT", "/operation_id", "operation reused with different content")
            return copy.deepcopy(old_head)
        current = self._heads.get(scope)
        current_generation = current.generation if current else 0
        if expected_generation != current_generation:
            _fail("E_CAS_CONFLICT", "/expected_generation", "approval head changed")
        head = ApprovalHead(scope, current_generation + 1, normalized, request_hash)
        self._heads[scope] = head
        self._history.setdefault(scope, []).append(head)
        self._operations[operation_id] = (scope, expected_generation, request_hash, head)
        return copy.deepcopy(head)

    def put_authorization(self, *, scope: str, operation_id: str, expected_generation: int,
                          record: Mapping[str, Any]) -> ApprovalHead:
        """Write a new v2 authorization after strict envelope validation."""
        normalized = validate_authorization(record)
        return self.put(scope=scope, operation_id=operation_id,
                        expected_generation=expected_generation, record=normalized)

    def revoke(self, *, scope: str, operation_id: str, expected_generation: int, reason: str) -> ApprovalHead:
        if operation_id in self._revoke_operations:
            old_scope, old_generation, old_reason, old_head = self._revoke_operations[operation_id]
            if (old_scope, old_generation, old_reason) != (scope, expected_generation, reason):
                _fail("E_IDEMPOTENCY_CONFLICT", "/operation_id", "revoke operation reused with different content")
            return copy.deepcopy(old_head)
        current = self._heads.get(scope)
        if current is None:
            _fail("E_APPROVAL_REFERENCE", "/scope", "approval head does not exist")
        record = copy.deepcopy(current.record)
        record["decision"] = "REVOKED"
        record["rationale"] = reason
        record["supersedes"] = {"generation": current.generation, "sha256": current.record_sha256}
        head = self.put(scope=scope, operation_id=operation_id, expected_generation=expected_generation, record=record)
        self._revoke_operations[operation_id] = (scope, expected_generation, reason, head)
        return copy.deepcopy(head)

    def head(self, scope: str) -> Optional[ApprovalHead]:
        return copy.deepcopy(self._heads.get(scope))

    def assert_current(self, *, scope: str, generation: int, record_sha256: str) -> ApprovalHead:
        """Return the approved head only when its generation and bytes match."""
        if type(generation) is not int or generation < 1 or not isinstance(record_sha256, str) or not HEX64.fullmatch(record_sha256):
            _fail("E_CURRENTNESS", "/head", "generation and record hash are required")
        head = self._heads.get(scope)
        if head is None or head.generation != generation or head.record_sha256 != record_sha256:
            _fail("E_CURRENTNESS", "/head", "approval head is stale")
        if head.record.get("decision") != "APPROVED":
            _fail("E_CURRENTNESS", "/head/decision", "approval is not currently approved")
        return copy.deepcopy(head)

    def history(self, scope: str) -> Tuple[ApprovalHead, ...]:
        return tuple(copy.deepcopy(self._history.get(scope, ())))

    def consume(self, *, scope: str, action: str, input_refs: Iterable[Mapping[str, Any]], now: Optional[datetime] = None) -> bool:
        head = self._heads.get(scope)
        if head is None or head.record["decision"] != "APPROVED":
            return False
        if action not in head.record["reviewed_actions"]:
            return False
        current_refs = {sha256(_ref(x, "/input_refs")) for x in input_refs}
        approved_refs = {sha256(x) for x in head.record["input_refs"]}
        if current_refs != approved_refs:
            return False
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None or now.utcoffset() is None:
            _fail("E_APPROVAL_TIME", "/now", "timezone-aware current time required")
        not_before = head.record.get("not_before")
        if not_before and now < datetime.fromisoformat(not_before.replace("Z", "+00:00")):
            return False
        expires = head.record.get("expires_at")
        if expires:
            try:
                if now >= datetime.fromisoformat(expires.replace("Z", "+00:00")):
                    return False
            except ValueError:
                return False
        return True

    def consume_once(self, *, scope: str, action: str, input_refs: Iterable[Mapping[str, Any]],
                     operation_id: str, expected_generation: int,
                     now: Optional[datetime] = None) -> bool:
        """Consume one approved input set exactly once with an idempotent key."""
        if not isinstance(scope, str) or not scope or not isinstance(action, str) or not action:
            _fail("E_CONSUME_SCHEMA", "/scope", "scope and action are required")
        if not isinstance(operation_id, str) or not operation_id:
            _fail("E_CONSUME_SCHEMA", "/operation_id", "operation id is required")
        if type(expected_generation) is not int or expected_generation < 1:
            _fail("E_CONSUME_SCHEMA", "/expected_generation", "positive generation required")
        refs = [_ref(value, "/input_refs") for value in input_refs]
        ref_hashes = [sha256(value) for value in refs]
        if len(ref_hashes) != len(set(ref_hashes)):
            _fail("E_CONSUME_BINDING", "/input_refs", "duplicate input reference")
        ref_hash = sha256(sorted(ref_hashes))
        request = (scope, action, ref_hash, expected_generation)
        existing = self._consumptions.get(operation_id)
        if existing is not None:
            if existing != request:
                _fail("E_IDEMPOTENCY_CONFLICT", "/operation_id", "consume operation reused with different content")
            return True
        head = self._heads.get(scope)
        if head is None or head.generation != expected_generation:
            _fail("E_CAS_CONFLICT", "/expected_generation", "approval head changed")
        consumed_key = (scope, action, ref_hash, head.generation)
        if consumed_key in self._consumed_keys:
            _fail("E_ALREADY_CONSUMED", "/input_refs", "approved input set was already consumed")
        if not self.consume(scope=scope, action=action, input_refs=refs, now=now):
            return False
        self._consumptions[operation_id] = request
        self._consumed_keys[consumed_key] = operation_id
        return True

    def lock(self, *, scope: str, receipt_id: str, operation_id: str, bindings: Iterable[Mapping[str, Any]]) -> InputLock:
        if not receipt_id or not operation_id:
            _fail("E_LOCK_BINDINGS", "/", "receipt and operation ids are required")
        head = self._heads.get(scope)
        if head is None or head.record["decision"] != "APPROVED":
            _fail("E_APPROVAL_CURRENT", "/scope", "an approved current head is required")
        rows = []
        for value in bindings:
            rows.append((_ref(value, "/bindings"), head.generation))
        binding_hash = sha256([{**ref, "binding_generation": gen} for ref, gen in rows])
        if operation_id in self._lock_operations:
            old_scope, old_receipt, old_binding_hash, old_lock = self._lock_operations[operation_id]
            if (old_scope, old_receipt, old_binding_hash) != (scope, receipt_id, binding_hash):
                _fail("E_IDEMPOTENCY_CONFLICT", "/operation_id", "lock operation reused with different content")
            return copy.deepcopy(old_lock)
        approved = {sha256(x) for x in head.record["input_refs"]}
        supplied = {sha256(x[0]) for x in rows}
        if not rows or supplied != approved:
            _fail("E_LOCK_BINDINGS", "/bindings", "bindings must exactly match approved input refs")
        if receipt_id in self._receipts:
            _fail("E_RECEIPT_CONFLICT", "/receipt_id", "receipt id is already bound")
        payload = {"record_type": "input-lock-receipt", "schema_version": 1, "receipt_id": receipt_id,
                   "approval_ref": {"scope": scope, "generation": head.generation, "sha256": head.record_sha256},
                   "bindings": [{"ref": ref, "binding_generation": gen} for ref, gen in rows],
                   "head_generation": head.generation}
        lock = InputLock(receipt_id, payload["approval_ref"], tuple(rows), head.generation, sha256(payload))
        self._lock_operations[operation_id] = (scope, receipt_id, binding_hash, lock)
        self._receipts[receipt_id] = lock
        return copy.deepcopy(lock)


__all__ = ["ApprovalHead", "ApprovalLedger", "AuthorizationError", "InputLock", "canonical_bytes", "sha256", "validate_approval", "validate_authorization"]
