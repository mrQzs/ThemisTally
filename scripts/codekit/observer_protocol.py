#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline protocol boundary for the optional project observer.

The observer is a read-only suggestion layer.  This module validates records
before a caller persists or displays them; it never calls a model, reads a
file, allocates budget, changes project state, or writes an observer result.
The request and output are intentionally closed records so an observer cannot
smuggle an approval, dispatch, or publication decision through a suggestion.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from typing import Any

from .planner_protocol import validate_resource_ref
from .protocols import DEFAULT_MAX_BYTES, DEFAULT_MAX_DEPTH, ProtocolError, strict_json_loads

OBSERVER_SCHEMA_VERSION = 1
MAX_ITEMS = 256
MAX_REFS = 512
MAX_TEXT = 16_384
_ID = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
_FORBIDDEN_STATUS = re.compile(
    r"\b(?:pass(?:ed)?|approved?|authori[sz](?:e|ed|ation)|published?|released?)\b",
    re.IGNORECASE,
)


def _pointer(base: str, key: str | int) -> str:
    token = str(key).replace("~", "~0").replace("/", "~1")
    return f"{base}/{token}" if base else f"/{token}"


def _fail(field: str, reason: str, code: str = "E_SCHEMA_FIELDS") -> None:
    raise ProtocolError(code, field=field or None, phase="observer", reason=reason)


def _obj(value: Any, field: str) -> dict[str, Any]:
    if type(value) is not dict:
        _fail(field, "object_required", "E_SCHEMA_TYPE")
    return value


def _array(value: Any, field: str, maximum: int = MAX_ITEMS) -> list[Any]:
    if type(value) is not list:
        _fail(field, "array_required", "E_SCHEMA_TYPE")
    if len(value) > maximum:
        _fail(field, "too_many_items")
    return value


def _closed(value: Mapping[str, Any], required: Iterable[str], optional: Iterable[str] = (), *, field: str = "") -> None:
    required = tuple(required)
    allowed = set(required) | set(optional)
    for name in required:
        if name not in value:
            _fail(_pointer(field, name), "missing_field")
    for name in value:
        if type(name) is not str or name not in allowed:
            _fail(_pointer(field, name), "unknown_field")


def _str(value: Any, field: str, *, maximum: int = MAX_TEXT, minimum: int = 1) -> str:
    if type(value) is not str:
        _fail(field, "string_required", "E_SCHEMA_TYPE")
    if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
        _fail(field, "unpaired_surrogate", "E_JSON_UNICODE")
    if not minimum <= len(value) <= maximum:
        _fail(field, "string_length_out_of_range")
    return value


def _id(value: Any, field: str) -> str:
    value = _str(value, field, maximum=64)
    if _ID.fullmatch(value) is None:
        _fail(field, "identifier_syntax", "E_ID_SYNTAX")
    return value


def _integer(value: Any, field: str, minimum: int = 0) -> int:
    if type(value) is not int:
        _fail(field, "exact_integer_required", "E_SCHEMA_TYPE")
    if value < minimum:
        _fail(field, "integer_out_of_range", "E_INTEGER_RANGE")
    return value


def _bool(value: Any, field: str) -> bool:
    if type(value) is not bool:
        _fail(field, "boolean_required", "E_SCHEMA_TYPE")
    return value


def _header(value: Mapping[str, Any], record_type: str) -> None:
    _closed(value, ("record_type", "schema_version"))
    if value["record_type"] != record_type:
        _fail("/record_type", "record_type_mismatch", "E_SCHEMA_RECORD_TYPE")
    _integer(value["schema_version"], "/schema_version", 1)
    if value["schema_version"] != OBSERVER_SCHEMA_VERSION:
        _fail("/schema_version", "unsupported_schema_version", "E_SCHEMA_VERSION_UNSUPPORTED")


def _ref(value: Any, field: str) -> dict[str, Any]:
    try:
        return validate_resource_ref(value, field=field)
    except ProtocolError:
        raise
    except (TypeError, ValueError) as exc:
        _fail(field, "resource_ref_invalid", "E_RESOURCE_FIELD")
        raise AssertionError from exc


def _refs(value: Any, field: str, *, minimum: int = 0) -> list[dict[str, Any]]:
    result = _array(value, field, MAX_REFS)
    if len(result) < minimum:
        _fail(field, "too_few_items")
    seen: set[tuple[str, str]] = set()
    output: list[dict[str, Any]] = []
    for index, item in enumerate(result):
        ref = _ref(item, _pointer(field, index))
        key = (ref["kind"], ref["id"])
        if key in seen:
            _fail(_pointer(field, index), "duplicate_resource_ref")
        seen.add(key)
        output.append(ref)
    return output


def _cursor(value: Any, field: str) -> dict[str, Any]:
    value = _obj(value, field)
    _closed(value, ("start", "end"), optional=("stream", "generation"), field=field)
    start = _integer(value["start"], _pointer(field, "start"))
    end = _integer(value["end"], _pointer(field, "end"))
    if end < start:
        _fail(_pointer(field, "end"), "cursor_end_before_start")
    if "stream" in value:
        _str(value["stream"], _pointer(field, "stream"), maximum=128)
    if "generation" in value:
        _integer(value["generation"], _pointer(field, "generation"))
    return copy.deepcopy(value)


def _same_ref(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    return all(left.get(key) == right.get(key) for key in ("kind", "id", "sha256", "path"))


def _ref_key(ref: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (ref["kind"], ref["id"], ref["sha256"], ref["path"])


def _check_claim_text(value: str, field: str) -> None:
    # A suggestion must never become a hidden PASS/approval channel.  Even a
    # negated claim is rejected here; the deterministic reviewer can state the
    # negative result in its own evidence record instead.
    if _FORBIDDEN_STATUS.search(value):
        _fail(field, "observer_cannot_claim_decision")


def _text_list(value: Any, field: str, *, minimum: int = 0) -> list[str]:
    result = _array(value, field)
    if len(result) < minimum:
        _fail(field, "too_few_items")
    out = []
    for index, item in enumerate(result):
        text = _str(item, _pointer(field, index))
        _check_claim_text(text, _pointer(field, index))
        out.append(text)
    return out


def _entry(item: Any, field: str, *, kind: str, optional: Iterable[str] = ()) -> dict[str, Any]:
    required = ["id", "text", "source_refs"]
    if kind == "hypothesis":
        required.extend(("missing_information", "verification_method"))
    elif kind == "risk":
        required.extend(("impact", "affected_task_ids"))
    elif kind in {"open_question", "suggested_next_action"}:
        required.append("affected_task_ids")
    if kind == "suggested_next_action":
        required.append("requires_authorization")
    item = _obj(item, field)
    _closed(item, required, optional=optional, field=field)
    _id(item["id"], _pointer(field, "id"))
    text = _str(item["text"], _pointer(field, "text"))
    _check_claim_text(text, _pointer(field, "text"))
    refs = _refs(item["source_refs"], _pointer(field, "source_refs"), minimum=1)
    if kind == "hypothesis":
        _text_list(item["missing_information"], _pointer(field, "missing_information"), minimum=1)
        _str(item["verification_method"], _pointer(field, "verification_method"))
        _check_claim_text(item["verification_method"], _pointer(field, "verification_method"))
    if kind == "risk":
        if item["impact"] not in {"low", "medium", "high", "unknown"}:
            _fail(_pointer(field, "impact"), "enum_value_not_allowed")
        _text_list(item["affected_task_ids"], _pointer(field, "affected_task_ids"))
    if kind == "open_question":
        _text_list(item["affected_task_ids"], _pointer(field, "affected_task_ids"))
    if kind == "suggested_next_action":
        _text_list(item["affected_task_ids"], _pointer(field, "affected_task_ids"))
        _bool(item["requires_authorization"], _pointer(field, "requires_authorization"))
    result = copy.deepcopy(item)
    result["source_refs"] = refs
    return result


def _validate_entries(value: Any, field: str, *, kind: str, optional: Iterable[str] = ()) -> list[dict[str, Any]]:
    result = _array(value, field)
    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for index, item in enumerate(result):
        normalized = _entry(item, _pointer(field, index), kind=kind, optional=optional)
        if normalized["id"] in seen:
            _fail(_pointer(field, index) + "/id", "duplicate_entry_id")
        seen.add(normalized["id"])
        output.append(normalized)
    return output


def validate_observer_request(value: Any) -> dict[str, Any]:
    """Validate an observer input request without invoking an observer."""
    value = _obj(value, "")
    required = (
        "record_type", "schema_version", "request_id", "source_cursor", "brief_ref",
        "source_refs", "output_limits", "profile_ref", "environment_ref",
        "timeout_seconds", "max_retries", "budget_reservation_ref",
    )
    _closed(value, required, optional=("project_id", "trigger", "observer_ref"))
    if value.get("record_type") != "observer-request":
        _fail("/record_type", "record_type_mismatch", "E_SCHEMA_RECORD_TYPE")
    _integer(value["schema_version"], "/schema_version", 1)
    if value["schema_version"] != OBSERVER_SCHEMA_VERSION:
        _fail("/schema_version", "unsupported_schema_version", "E_SCHEMA_VERSION_UNSUPPORTED")
    _id(value["request_id"], "/request_id")
    if "project_id" in value:
        _id(value["project_id"], "/project_id")
    if "observer_ref" in value:
        _id(value["observer_ref"], "/observer_ref")
    if "trigger" in value:
        if value["trigger"] not in {"threshold", "stage_boundary", "explicit_request", "recovery"}:
            _fail("/trigger", "enum_value_not_allowed")
    cursor = _cursor(value["source_cursor"], "/source_cursor")
    brief_ref = _ref(value["brief_ref"], "/brief_ref")
    refs = _refs(value["source_refs"], "/source_refs")
    if any(_same_ref(brief_ref, ref) for ref in refs):
        _fail("/source_refs", "brief_ref_must_not_be_duplicated")
    limits = _obj(value["output_limits"], "/output_limits")
    _closed(limits, ("max_bytes", "max_items"), optional=("max_text",), field="/output_limits")
    _integer(limits["max_bytes"], "/output_limits/max_bytes", 1)
    _integer(limits["max_items"], "/output_limits/max_items", 1)
    if "max_text" in limits:
        _integer(limits["max_text"], "/output_limits/max_text", 1)
    for name in ("profile_ref", "environment_ref", "budget_reservation_ref"):
        if value[name] is not None:
            _ref(value[name], "/" + name)
    _integer(value["timeout_seconds"], "/timeout_seconds", 1)
    _integer(value["max_retries"], "/max_retries", 0)
    return {**copy.deepcopy(value), "source_cursor": cursor, "brief_ref": brief_ref, "source_refs": refs}


def validate_observer_suggestion(value: Any, *, allowed_refs: Iterable[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """Validate one suggestion record; suggestions never carry a decision."""
    value = _obj(value, "")
    _closed(value, ("record_type", "schema_version", "suggestion_id", "request_id", "category", "text", "source_refs", "affected_task_ids", "requires_authorization"))
    if value["record_type"] != "observer-suggestion":
        _fail("/record_type", "record_type_mismatch", "E_SCHEMA_RECORD_TYPE")
    _integer(value["schema_version"], "/schema_version", 1)
    if value["schema_version"] != OBSERVER_SCHEMA_VERSION:
        _fail("/schema_version", "unsupported_schema_version", "E_SCHEMA_VERSION_UNSUPPORTED")
    _id(value["suggestion_id"], "/suggestion_id"); _id(value["request_id"], "/request_id")
    if value["category"] not in {"hypothesis", "risk", "open_question", "suggested_next_action"}:
        _fail("/category", "enum_value_not_allowed")
    text = _str(value["text"], "/text"); _check_claim_text(text, "/text")
    refs = _refs(value["source_refs"], "/source_refs", minimum=1)
    _text_list(value["affected_task_ids"], "/affected_task_ids")
    _bool(value["requires_authorization"], "/requires_authorization")
    _assert_refs_allowed(refs, allowed_refs, field="/source_refs")
    return {**copy.deepcopy(value), "source_refs": refs}


def _assert_refs_allowed(refs: Iterable[Mapping[str, Any]], allowed_refs: Iterable[Mapping[str, Any]] | None, *, field: str) -> None:
    if allowed_refs is None:
        return
    allowed = {_ref_key(_ref(ref, field)) for ref in allowed_refs}
    for index, ref in enumerate(refs):
        if _ref_key(ref) not in allowed:
            _fail(_pointer(field, index), "source_ref_not_in_request", "E_CONTEXT_BINDING")


def validate_observer_output(value: Any, *, request: Mapping[str, Any] | None = None,
                             available_refs: Iterable[Mapping[str, Any]] | Mapping[Any, Any] | None = None) -> dict[str, Any]:
    """Validate observer output and, when supplied, bind every citation to input.

    ``available_refs`` is an optional trusted registry used by an integration
    layer.  The protocol itself only compares immutable ResourceRef tuples; it
    never opens paths or fetches bytes.
    """
    value = _obj(value, "")
    required = ("record_type", "schema_version", "request_id", "source_cursor", "brief_ref", "facts", "hypotheses", "risks", "open_questions", "suggested_next_actions", "omitted")
    _closed(value, required, optional=("status", "suggestions"))
    if value["record_type"] != "observer-output":
        _fail("/record_type", "record_type_mismatch", "E_SCHEMA_RECORD_TYPE")
    _integer(value["schema_version"], "/schema_version", 1)
    if value["schema_version"] != OBSERVER_SCHEMA_VERSION:
        _fail("/schema_version", "unsupported_schema_version", "E_SCHEMA_VERSION_UNSUPPORTED")
    request_id = _id(value["request_id"], "/request_id")
    cursor = _cursor(value["source_cursor"], "/source_cursor")
    brief_ref = _ref(value["brief_ref"], "/brief_ref")
    facts = _validate_entries(value["facts"], "/facts", kind="fact")
    hypotheses = _validate_entries(value["hypotheses"], "/hypotheses", kind="hypothesis", optional=("missing_information", "verification_method"))
    risks = _validate_entries(value["risks"], "/risks", kind="risk", optional=("impact", "affected_task_ids"))
    questions = _validate_entries(value["open_questions"], "/open_questions", kind="open_question", optional=("affected_task_ids",))
    actions = _validate_entries(value["suggested_next_actions"], "/suggested_next_actions", kind="suggested_next_action", optional=("affected_task_ids", "requires_authorization"))
    omitted = _array(value["omitted"], "/omitted")
    omitted_out: list[dict[str, Any]] = []
    seen_omitted: set[str] = set()
    for index, item in enumerate(omitted):
        field = _pointer("/omitted", index); item = _obj(item, field)
        _closed(item, ("id", "reason"), optional=("source_refs", "item_ids"), field=field)
        iid = _id(item["id"], _pointer(field, "id")); reason = _str(item["reason"], _pointer(field, "reason"))
        _check_claim_text(reason, _pointer(field, "reason"))
        if iid in seen_omitted:
            _fail(_pointer(field, "id"), "duplicate_entry_id")
        seen_omitted.add(iid)
        refs = _refs(item.get("source_refs", []), _pointer(field, "source_refs"))
        ids = _text_list(item.get("item_ids", []), _pointer(field, "item_ids"))
        omitted_out.append({**copy.deepcopy(item), "id": iid, "source_refs": refs, "item_ids": ids})
    if "status" in value:
        if value["status"] not in {"OK", "PARTIAL", "DEGRADED", "REJECTED"}:
            _fail("/status", "observer_status_not_allowed")
    if "suggestions" in value:
        suggestions = _array(value["suggestions"], "/suggestions")
        suggestions_out = [validate_observer_suggestion(item, allowed_refs=None) for item in suggestions]
    else:
        suggestions_out = None
    all_ids: set[str] = set()
    for collection_name, entries in (("facts", facts), ("hypotheses", hypotheses), ("risks", risks),
                                     ("open_questions", questions), ("suggested_next_actions", actions)):
        for index, item in enumerate(entries):
            if item["id"] in all_ids:
                _fail(f"/{collection_name}/{index}/id", "duplicate_context_entry_id")
            all_ids.add(item["id"])
    if suggestions_out is not None:
        for index, item in enumerate(suggestions_out):
            if item["suggestion_id"] in all_ids:
                _fail(f"/suggestions/{index}/suggestion_id", "duplicate_context_entry_id")
            all_ids.add(item["suggestion_id"])
    for index, item in enumerate(omitted_out):
        if item["id"] in all_ids:
            _fail(f"/omitted/{index}/id", "duplicate_context_entry_id")
        all_ids.add(item["id"])
    refs_for_output: list[dict[str, Any]] = [brief_ref]
    for entries in (facts, hypotheses, risks, questions, actions):
        for item in entries:
            refs_for_output.extend(item["source_refs"])
    for item in omitted_out:
        refs_for_output.extend(item["source_refs"])
    if suggestions_out is not None:
        for item in suggestions_out:
            refs_for_output.extend(item["source_refs"])
    if request is not None:
        normalized_request = validate_observer_request(request)
        if request_id != normalized_request["request_id"]:
            _fail("/request_id", "request_output_id_mismatch", "E_CONTEXT_BINDING")
        if cursor != normalized_request["source_cursor"]:
            _fail("/source_cursor", "output_cursor_mismatch", "E_CONTEXT_BINDING")
        if not _same_ref(brief_ref, normalized_request["brief_ref"]):
            _fail("/brief_ref", "output_brief_ref_mismatch", "E_CONTEXT_BINDING")
        allowed_refs = [normalized_request["brief_ref"], *normalized_request["source_refs"]]
        for index, ref in enumerate(refs_for_output):
            _assert_refs_allowed([ref], allowed_refs, field=f"/output_refs/{index}")
    if available_refs is not None:
        _assert_refs_exist(refs_for_output, available_refs)
    result = {**copy.deepcopy(value), "request_id": request_id, "source_cursor": cursor,
              "brief_ref": brief_ref, "facts": facts, "hypotheses": hypotheses,
              "risks": risks, "open_questions": questions,
              "suggested_next_actions": actions, "omitted": omitted_out}
    if suggestions_out is not None:
        result["suggestions"] = suggestions_out
    return result


def _assert_refs_exist(refs: Iterable[Mapping[str, Any]], available_refs: Iterable[Mapping[str, Any]] | Mapping[Any, Any]) -> None:
    trusted: set[tuple[str, str, str, str]] = set()
    trusted_digest: set[tuple[str, str, str]] = set()
    if isinstance(available_refs, Mapping):
        for key, item in available_refs.items():
            if isinstance(item, Mapping) and "kind" in item:
                normalized = _ref(item, "/available_refs")
                trusted.add(_ref_key(normalized))
            elif isinstance(item, bytes) and isinstance(key, tuple) and len(key) >= 2:
                # A trusted byte registry may key entries by (kind, id).  The
                # path is intentionally not guessed; digest and identity still
                # prove the immutable bytes, while the normal ResourceRef
                # validator enforces the caller-provided path.
                kind, ident = key[0], key[1]
                if isinstance(kind, str) and isinstance(ident, str):
                    trusted_digest.add((kind, ident, hashlib.sha256(item).hexdigest()))
    else:
        for item in available_refs:
            if isinstance(item, Mapping) and "kind" in item:
                normalized = _ref(item, "/available_refs")
                trusted.add(_ref_key(normalized))
    for ref in refs:
        if _ref_key(ref) not in trusted and (ref["kind"], ref["id"], ref["sha256"]) not in trusted_digest:
            _fail("/source_refs", "source_ref_missing", "E_RESOURCE_MISSING")


def validate_observer_source_ref(ref: Any, *, source_bytes: bytes | None = None) -> dict[str, Any]:
    """Validate a ResourceRef and, when bytes are available, lock its digest.

    No path is opened here.  The caller supplies the exact UTF-8 bytes from a
    trusted evidence registry, keeping observer validation deterministic and
    read-only.
    """
    normalized = _ref(ref, "/ref")
    if source_bytes is not None:
        if type(source_bytes) is not bytes:
            _fail("/source_bytes", "bytes_required", "E_RESOURCE_BYTES")
        if hashlib.sha256(source_bytes).hexdigest() != normalized["sha256"]:
            _fail("/ref/sha256", "source_digest_mismatch", "E_RESOURCE_HASH_MISMATCH")
    return normalized


def validate_observer_binding(request: Any, output: Any, *, available_refs: Iterable[Mapping[str, Any]] | Mapping[Any, Any] | None = None) -> dict[str, Any]:
    """Validate request/output identity and citation closure in one call."""
    normalized_request = validate_observer_request(request)
    normalized_output = validate_observer_output(output, request=normalized_request, available_refs=available_refs)
    return {"request": normalized_request, "output": normalized_output}


def strict_observer_json_loads(raw: bytes, *, max_bytes: int = DEFAULT_MAX_BYTES, max_depth: int = DEFAULT_MAX_DEPTH) -> dict[str, Any]:
    value = strict_json_loads(raw, max_bytes=max_bytes, max_depth=max_depth)
    if type(value) is not dict:
        _fail("", "observer_record_must_be_object", "E_SCHEMA_TYPE")
    return value


def canonical_observer_bytes(value: Mapping[str, Any]) -> bytes:
    """Canonical bytes for deterministic fixtures; no persistence side effect."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def observer_digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_observer_bytes(value)).hexdigest()


# Short aliases used by early offline fixtures.
validate_request = validate_observer_request
validate_output = validate_observer_output
ObserverProtocolError = ProtocolError

__all__ = [
    "OBSERVER_SCHEMA_VERSION", "ObserverProtocolError", "validate_observer_request",
    "validate_observer_suggestion", "validate_observer_output", "validate_observer_binding",
    "validate_observer_source_ref",
    "strict_observer_json_loads", "canonical_observer_bytes", "observer_digest",
    "validate_request", "validate_output",
]
