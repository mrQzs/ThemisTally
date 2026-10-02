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
    if ".." in value["path"].replace("\\", "/").split("/"):
        _fail("E_RESOURCE_PATH", f"{path}/path", "path traversal is forbidden")
    return copy.deepcopy(value)


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
        self._operations: Dict[str, Tuple[str, ApprovalHead]] = {}

    def put(self, *, scope: str, operation_id: str, expected_generation: int, record: Mapping[str, Any]) -> ApprovalHead:
        if not scope or not operation_id:
            _fail("E_APPROVAL_SCHEMA", "/", "scope and operation_id are required")
        normalized = validate_approval(record)
        request_hash = sha256(normalized)
        if operation_id in self._operations:
            old_hash, old_head = self._operations[operation_id]
            if old_hash != request_hash:
                _fail("E_IDEMPOTENCY_CONFLICT", "/operation_id", "operation reused with different content")
            return old_head
        current = self._heads.get(scope)
        current_generation = current.generation if current else 0
        if expected_generation != current_generation:
            _fail("E_CAS_CONFLICT", "/expected_generation", "approval head changed")
        head = ApprovalHead(scope, current_generation + 1, normalized, request_hash)
        self._heads[scope] = head
        self._history.setdefault(scope, []).append(head)
        self._operations[operation_id] = (request_hash, head)
        return head

    def revoke(self, *, scope: str, operation_id: str, expected_generation: int, reason: str) -> ApprovalHead:
        current = self._heads.get(scope)
        if current is None:
            _fail("E_APPROVAL_REFERENCE", "/scope", "approval head does not exist")
        record = copy.deepcopy(current.record)
        record["decision"] = "REVOKED"
        record["rationale"] = reason
        record["supersedes"] = {"generation": current.generation, "sha256": current.record_sha256}
        return self.put(scope=scope, operation_id=operation_id, expected_generation=expected_generation, record=record)

    def head(self, scope: str) -> Optional[ApprovalHead]:
        return self._heads.get(scope)

    def history(self, scope: str) -> Tuple[ApprovalHead, ...]:
        return tuple(self._history.get(scope, ()))

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
        expires = head.record.get("expires_at")
        if expires:
            try:
                if now >= datetime.fromisoformat(expires.replace("Z", "+00:00")):
                    return False
            except ValueError:
                return False
        return True

    def lock(self, *, scope: str, receipt_id: str, operation_id: str, bindings: Iterable[Mapping[str, Any]]) -> InputLock:
        head = self._heads.get(scope)
        if head is None or head.record["decision"] != "APPROVED":
            _fail("E_APPROVAL_CURRENT", "/scope", "an approved current head is required")
        rows = []
        for value in bindings:
            rows.append((_ref(value, "/bindings"), head.generation))
        payload = {"record_type": "input-lock-receipt", "schema_version": 1, "receipt_id": receipt_id,
                   "approval_ref": {"scope": scope, "generation": head.generation, "sha256": head.record_sha256},
                   "bindings": [{"ref": ref, "binding_generation": gen} for ref, gen in rows],
                   "head_generation": head.generation}
        return InputLock(receipt_id, payload["approval_ref"], tuple(rows), head.generation, sha256(payload))


__all__ = ["ApprovalHead", "ApprovalLedger", "AuthorizationError", "InputLock", "canonical_bytes", "sha256", "validate_approval"]
