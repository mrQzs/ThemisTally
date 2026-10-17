"""Immutable acceptance and input-binding records for workflow outputs.

The module proves only structural provenance and revocation decisions.  It does
not run checks, inspect Git, authenticate a reviewer, or make an output
available to an executor by itself.  Every reference is fixed by identity;
``latest`` and other mutable aliases are rejected at the boundary.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from . import protocols

ACCEPTED_RESULT_TYPE = "accepted-result"
ACCEPTANCE_REVOCATION_TYPE = "acceptance-revocation"
ACCEPTANCE_SCHEMA_VERSION = 1
MAX_OUTPUTS = 256
MAX_UPSTREAMS = 256


@dataclass(frozen=True)
class AcceptedResult:
    record: Mapping[str, Any]

    @property
    def acceptance_id(self) -> str:
        return self.record["acceptance_id"]

    @property
    def request_id(self) -> str:
        return self.record["request_id"]

    @property
    def task_id(self) -> str:
        return self.record["task_id"]

    @property
    def plan_version(self) -> int:
        return self.record["plan_version"]

    @property
    def guard_version(self) -> int:
        return self.record["guard_version"]


@dataclass(frozen=True)
class InputBindingReceipt:
    record: Mapping[str, Any]

    @property
    def upstream_acceptance_id(self) -> str:
        return self.record["upstream_acceptance_id"]

    @property
    def request_id(self) -> str:
        return self.record["request_id"]

    @property
    def task_id(self) -> str:
        return self.record["task_id"]


@dataclass(frozen=True)
class AcceptanceRevocation:
    record: Mapping[str, Any]

    @property
    def revocation_id(self) -> str:
        return self.record["revocation_id"]

    @property
    def acceptance_id(self) -> str:
        return self.record["acceptance_id"]


@dataclass(frozen=True)
class BindingDecision:
    decision: str
    reasons: tuple[str, ...] = ()
    acceptance_id: str | None = None


def validate_accepted_result(document: Any) -> AcceptedResult:
    protocols.check_json_value(document, max_bytes=protocols.DEFAULT_MAX_BYTES)
    root = _expect_dict(document, "", "accepted_result")
    _closed(root, {
        "record_type", "schema_version", "acceptance_id", "request_id", "task_id",
        "plan_version", "guard_version", "candidate_ref", "check_set_ref", "verdict_ref",
        "output_refs", "target_schema_refs", "upstream_acceptance_ids",
    })
    _const(root, "record_type", ACCEPTED_RESULT_TYPE)
    protocols.require_schema_version(root, {ACCEPTANCE_SCHEMA_VERSION})
    _id(root.get("acceptance_id"), "/acceptance_id")
    protocols.validate_request_id(root.get("request_id"), field="/request_id")
    protocols.validate_task_id(root.get("task_id"), field="/task_id")
    _positive(root.get("plan_version"), "/plan_version")
    _positive(root.get("guard_version"), "/guard_version")
    candidate = _validate_ref(root.get("candidate_ref"), "/candidate_ref")
    check_set = _validate_ref(root.get("check_set_ref"), "/check_set_ref")
    verdict = _validate_ref(root.get("verdict_ref"), "/verdict_ref")
    outputs = _validate_ref_map(root.get("output_refs"), "/output_refs", nonempty=True)
    target_schemas = _validate_ref_map(root.get("target_schema_refs"), "/target_schema_refs", nonempty=True)
    if set(outputs) != set(target_schemas):
        _error("E_ACCEPTANCE_BINDING", "/target_schema_refs", "output_schema_port_mismatch")
    upstream = root.get("upstream_acceptance_ids")
    if type(upstream) is not list or len(upstream) > MAX_UPSTREAMS:
        _error("E_SCHEMA_TYPE", "/upstream_acceptance_ids", "array_required")
    upstream_ids = []
    for index, value in enumerate(upstream):
        upstream_ids.append(_id(value, f"/upstream_acceptance_ids/{index}"))
    if len(set(upstream_ids)) != len(upstream_ids):
        _error("E_ACCEPTANCE_BINDING", "/upstream_acceptance_ids", "duplicate_upstream")
    normalized = {
        "record_type": ACCEPTED_RESULT_TYPE,
        "schema_version": ACCEPTANCE_SCHEMA_VERSION,
        "acceptance_id": root["acceptance_id"],
        "request_id": root["request_id"],
        "task_id": root["task_id"],
        "plan_version": root["plan_version"],
        "guard_version": root["guard_version"],
        "candidate_ref": candidate,
        "check_set_ref": check_set,
        "verdict_ref": verdict,
        "output_refs": outputs,
        "target_schema_refs": target_schemas,
        "upstream_acceptance_ids": upstream_ids,
    }
    return AcceptedResult(_freeze(copy.deepcopy(normalized)))


def validate_input_binding_receipt(document: Any) -> InputBindingReceipt:
    protocols.check_json_value(document, max_bytes=protocols.DEFAULT_MAX_BYTES)
    root = _expect_dict(document, "", "input_binding")
    _closed(root, {
        "record_type", "schema_version", "request_id", "task_id", "plan_version", "source_plan_version",
        "guard_version", "source_guard_version", "source_task_id", "source_port", "upstream_acceptance_id",
        "candidate_ref", "output_ref", "target_schema_ref", "check_set_ref",
    })
    _const(root, "record_type", "input-binding-receipt")
    protocols.require_schema_version(root, {ACCEPTANCE_SCHEMA_VERSION})
    protocols.validate_request_id(root.get("request_id"), field="/request_id")
    protocols.validate_task_id(root.get("task_id"), field="/task_id")
    _positive(root.get("plan_version"), "/plan_version")
    _positive(root.get("source_plan_version"), "/source_plan_version")
    _positive(root.get("source_guard_version"), "/source_guard_version")
    _positive(root.get("guard_version"), "/guard_version")
    protocols.validate_task_id(root.get("source_task_id"), field="/source_task_id")
    protocols.validate_logical_id(root.get("source_port"), field="/source_port")
    _id(root.get("upstream_acceptance_id"), "/upstream_acceptance_id")
    normalized = {
        "record_type": "input-binding-receipt", "schema_version": ACCEPTANCE_SCHEMA_VERSION,
        "request_id": root["request_id"], "task_id": root["task_id"],
        "plan_version": root["plan_version"], "source_plan_version": root["source_plan_version"],
        "guard_version": root["guard_version"],
        "source_guard_version": root["source_guard_version"],
        "source_task_id": root["source_task_id"], "source_port": root["source_port"],
        "upstream_acceptance_id": root["upstream_acceptance_id"],
        "candidate_ref": _validate_ref(root.get("candidate_ref"), "/candidate_ref"),
        "output_ref": _validate_ref(root.get("output_ref"), "/output_ref"),
        "target_schema_ref": _validate_ref(root.get("target_schema_ref"), "/target_schema_ref"),
        "check_set_ref": _validate_ref(root.get("check_set_ref"), "/check_set_ref"),
    }
    return InputBindingReceipt(_freeze(copy.deepcopy(normalized)))


def validate_acceptance_revocation(document: Any) -> AcceptanceRevocation:
    protocols.check_json_value(document, max_bytes=protocols.DEFAULT_MAX_BYTES)
    root = _expect_dict(document, "", "acceptance_revocation")
    _closed(root, {"record_type", "schema_version", "revocation_id", "acceptance_id", "reason", "guard_version", "evidence_ref"})
    _const(root, "record_type", ACCEPTANCE_REVOCATION_TYPE)
    protocols.require_schema_version(root, {ACCEPTANCE_SCHEMA_VERSION})
    _id(root.get("revocation_id"), "/revocation_id")
    _id(root.get("acceptance_id"), "/acceptance_id")
    _id(root.get("reason"), "/reason")
    _positive(root.get("guard_version"), "/guard_version")
    _id(root.get("evidence_ref"), "/evidence_ref")
    return AcceptanceRevocation(_freeze(copy.deepcopy({
        "record_type": ACCEPTANCE_REVOCATION_TYPE, "schema_version": ACCEPTANCE_SCHEMA_VERSION,
        "revocation_id": root["revocation_id"], "acceptance_id": root["acceptance_id"],
        "reason": root["reason"], "guard_version": root["guard_version"],
        "evidence_ref": root["evidence_ref"],
    })))


def resolve_input_binding(receipt: InputBindingReceipt | Mapping[str, Any],
                          accepted_results: Sequence[AcceptedResult | Mapping[str, Any]],
                          revocations: Sequence[AcceptanceRevocation | Mapping[str, Any]] = (),
                          *, expected_request_id: str, expected_task_id: str,
                          expected_plan_version: int, expected_guard_version: int) -> BindingDecision:
    """Resolve one fixed input against immutable acceptance history."""
    # Dataclass construction is not validation: recheck even wrapped records.
    receipt_obj = validate_input_binding_receipt(_thaw(receipt.record if isinstance(receipt, InputBindingReceipt) else receipt))
    protocols.validate_request_id(expected_request_id, field="/expected_request_id")
    protocols.validate_task_id(expected_task_id, field="/expected_task_id")
    _positive(expected_plan_version, "/expected_plan_version")
    _positive(expected_guard_version, "/expected_guard_version")
    record = receipt_obj.record
    if (record["request_id"], record["task_id"], record["plan_version"], record["guard_version"]) != (
            expected_request_id, expected_task_id, expected_plan_version, expected_guard_version):
        return BindingDecision("BLOCK", ("TARGET_BINDING_MISMATCH",), receipt_obj.upstream_acceptance_id)
    for values, field in ((accepted_results, "/accepted_results"), (revocations, "/revocations")):
        if type(values) not in (tuple, list) or len(values) > 1024:
            _error("E_SCHEMA_TYPE", field, "bounded_array_required")
    accepted = {}
    for value in accepted_results:
        item = validate_accepted_result(_thaw(value.record if isinstance(value, AcceptedResult) else value))
        old = accepted.get(item.acceptance_id)
        if old is not None and old.record != item.record:
            _error("E_SCHEMA_FIELDS", "/accepted_results", "acceptance_id_conflict")
        accepted[item.acceptance_id] = item
    invalidated = set()
    revocation_ids = {}
    for value in revocations:
        item = validate_acceptance_revocation(_thaw(value.record if isinstance(value, AcceptanceRevocation) else value))
        old = revocation_ids.get(item.revocation_id)
        if old is not None and old.record != item.record:
            _error("E_SCHEMA_FIELDS", "/revocations", "revocation_id_conflict")
        revocation_ids[item.revocation_id] = item
        invalidated.add(item.acceptance_id)
    if receipt_obj.upstream_acceptance_id not in accepted:
        return BindingDecision("BLOCK", ("ACCEPTANCE_UNKNOWN",), receipt_obj.upstream_acceptance_id)
    result = accepted[receipt_obj.upstream_acceptance_id]
    # Iterative closure walk avoids recursion limits on long workflow chains.
    pending = [(result.acceptance_id, False)]
    visiting, done = set(), set()
    while pending:
        identity, leaving = pending.pop()
        if leaving:
            visiting.remove(identity)
            done.add(identity)
            continue
        if identity in invalidated:
            return BindingDecision("BLOCK", ("ACCEPTANCE_REVOKED",), result.acceptance_id)
        if identity not in accepted:
            return BindingDecision("BLOCK", ("UPSTREAM_ACCEPTANCE_UNKNOWN",), result.acceptance_id)
        if identity in visiting:
            return BindingDecision("BLOCK", ("ACCEPTANCE_CYCLE",), result.acceptance_id)
        if identity in done:
            continue
        if accepted[identity].request_id != expected_request_id:
            return BindingDecision("BLOCK", ("REQUEST_MISMATCH",), result.acceptance_id)
        visiting.add(identity)
        pending.append((identity, True))
        pending.extend((upstream, False) for upstream in reversed(accepted[identity].record["upstream_acceptance_ids"]))
    if result.guard_version != record["source_guard_version"]:
        return BindingDecision("BLOCK", ("SOURCE_GUARD_MISMATCH",), result.acceptance_id)
    if result.request_id != record["request_id"]:
        return BindingDecision("BLOCK", ("REQUEST_MISMATCH",), result.acceptance_id)
    if result.task_id != record["source_task_id"]:
        return BindingDecision("BLOCK", ("SOURCE_TASK_MISMATCH",), result.acceptance_id)
    if result.plan_version != record["source_plan_version"]:
        return BindingDecision("BLOCK", ("PLAN_MISMATCH",), result.acceptance_id)
    if not _same_ref(result.record["candidate_ref"], record["candidate_ref"]):
        return BindingDecision("BLOCK", ("CANDIDATE_MISMATCH",), result.acceptance_id)
    source_port = record["source_port"]
    if source_port not in result.record["output_refs"]:
        return BindingDecision("BLOCK", ("OUTPUT_PORT_UNKNOWN",), result.acceptance_id)
    if not _same_ref(result.record["output_refs"][source_port], record["output_ref"]):
        return BindingDecision("BLOCK", ("OUTPUT_MISMATCH",), result.acceptance_id)
    if not _same_ref(result.record["target_schema_refs"][source_port], record["target_schema_ref"]):
        return BindingDecision("BLOCK", ("TARGET_SCHEMA_MISMATCH",), result.acceptance_id)
    if not _same_ref(result.record["check_set_ref"], record["check_set_ref"]):
        return BindingDecision("BLOCK", ("CHECK_SET_MISMATCH",), result.acceptance_id)
    return BindingDecision("BOUND", (), result.acceptance_id)


def resolve_input_bindings(receipts: Sequence[InputBindingReceipt | Mapping[str, Any]],
                           accepted_results: Sequence[AcceptedResult | Mapping[str, Any]],
                           revocations: Sequence[AcceptanceRevocation | Mapping[str, Any]] = (),
                           *, expected_request_id: str, expected_task_id: str,
                           expected_plan_version: int, expected_guard_version: int) -> tuple[BindingDecision, ...]:
    """Resolve all inputs; one revoked/mismatched upstream remains a block."""
    if type(receipts) not in (tuple, list) or len(receipts) > MAX_UPSTREAMS:
        _error("E_SCHEMA_TYPE", "/receipts", "bounded_array_required")
    return tuple(resolve_input_binding(item, accepted_results, revocations,
                                       expected_request_id=expected_request_id, expected_task_id=expected_task_id,
                                       expected_plan_version=expected_plan_version, expected_guard_version=expected_guard_version)
                 for item in receipts)


def _validate_ref(value: Any, field: str) -> dict[str, str]:
    obj = _expect_dict(value, field, "ref")
    _closed(obj, {"kind", "id", "sha256", "path"})
    protocols.validate_resource_kind(obj.get("kind"), field=f"{field}/kind")
    ref_id = protocols.validate_logical_id(obj.get("id"), field=f"{field}/id")
    if ref_id.lower() in {"latest", "head", "current"}:
        _error("E_MUTABLE_REF", f"{field}/id", "mutable_alias_forbidden")
    protocols.validate_sha256(obj.get("sha256"), field=f"{field}/sha256")
    protocols.validate_business_path(obj.get("path"), field=f"{field}/path")
    return {"kind": obj["kind"], "id": ref_id, "sha256": obj["sha256"], "path": obj["path"]}


def _validate_ref_map(value: Any, field: str, *, nonempty: bool = False) -> dict[str, dict[str, str]]:
    obj = _expect_dict(value, field, "ref_map")
    if nonempty and not obj:
        _error("E_SCHEMA_FIELDS", field, "nonempty_object_required")
    if len(obj) > MAX_OUTPUTS:
        _error("E_JSON_LIMIT", field, "ref_map_limit_exceeded")
    result = {}
    for key, ref in obj.items():
        protocols.validate_logical_id(key, field=f"{field}/{key}")
        if key in result:
            _error("E_SCHEMA_FIELDS", field, "duplicate_port")
        result[key] = _validate_ref(ref, f"{field}/{key}")
    return result


def _same_ref(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    # The path is part of a ResourceRef's fixed binding.  The digest proves
    # the bytes, while the path identifies which declared port/source was
    # bound; silently accepting a path-only change would permit an artifact to
    # be relabelled under a different location without a new receipt.
    return all(left.get(name) == right.get(name)
               for name in ("kind", "id", "sha256", "path"))


def _id(value: Any, field: str) -> str:
    result = protocols.validate_logical_id(value, field=field)
    if result.lower() in {"latest", "head", "current"}:
        _error("E_MUTABLE_REF", field, "mutable_alias_forbidden")
    return result


def _positive(value: Any, field: str) -> int:
    return protocols.require_int(value, field=field, minimum=1)


def _expect_dict(value: Any, field: str, reason: str) -> dict[str, Any]:
    if type(value) is not dict:
        _error("E_SCHEMA_TYPE", field, f"{reason}_object_required")
    return value


def _closed(value: Mapping[str, Any], allowed: set[str], field: str = "") -> None:
    if set(value) != allowed:
        _error("E_SCHEMA_FIELDS", field, "closed_object_fields")


def _const(value: Mapping[str, Any], field: str, expected: Any) -> None:
    if value.get(field) != expected:
        _error("E_SCHEMA_FIELDS", f"/{field}", "constant_mismatch")


def _error(code: str, field: str, reason: str) -> None:
    # Use the established registry; local mismatch details belong in reason.
    if code in {"E_ACCEPTANCE_BINDING", "E_MUTABLE_REF"}:
        code = "E_SCHEMA_FIELDS"
    raise protocols.ProtocolError(code, field=field or None, phase="acceptance", reason=reason)


def _freeze(value: Any) -> Any:
    if type(value) is dict:
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if type(value) is list:
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: Any, *, depth: int = 0, active: set[int] | None = None,
          remaining: list[int] | None = None) -> Any:
    remaining = [protocols.DEFAULT_MAX_BYTES] if remaining is None else remaining
    remaining[0] -= max(1, len(value)) if type(value) is str else 1
    if remaining[0] < 0:
        _error("E_JSON_LIMIT", "", "materialized_size_limit_exceeded")
    if isinstance(value, Mapping) or type(value) in (tuple, list):
        active = set() if active is None else active
        identity = id(value)
        if identity in active:
            _error("E_JSON_CYCLE", "", "cyclic_container")
        if depth >= protocols.DEFAULT_MAX_DEPTH:
            _error("E_JSON_LIMIT", "", "nesting_limit_exceeded")
        active.add(identity)
        try:
            if isinstance(value, Mapping):
                return {key: _thaw(item, depth=depth + 1, active=active, remaining=remaining)
                        for key, item in value.items()}
            return [_thaw(item, depth=depth + 1, active=active, remaining=remaining) for item in value]
        finally:
            active.remove(identity)
    return value


__all__ = [
    "ACCEPTANCE_REVOCATION_TYPE", "ACCEPTANCE_SCHEMA_VERSION", "ACCEPTED_RESULT_TYPE",
    "AcceptedResult", "AcceptanceRevocation", "BindingDecision", "InputBindingReceipt",
    "resolve_input_binding", "resolve_input_bindings", "validate_accepted_result",
    "validate_acceptance_revocation", "validate_input_binding_receipt",
]
