"""Offline ``repo-analysis`` artifact builder.

The analysis plugin only records facts supplied by its caller.  It does not
inspect a repository, invoke a model, or decide whether an inference is true.
That boundary keeps a replayable report separate from the core scheduler's
candidate, authorization, and verdict records.
"""

from __future__ import annotations

import copy
import re
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence

from .builtin_artifacts import ArtifactError, digest, resource_ref, source_anchor, validate_artifact


ANALYSIS_RECORD_TYPE = "analysis-report"
ANALYSIS_STATUSES = {"DRAFT_VALIDATED", "READY", "UNKNOWN", "BLOCKED", "NOT_RUN", "REFERENCE_ONLY"}
EVIDENCE_CLASSES = {"OFFLINE_FIXTURE", "LOCAL_REFERENCE", "SYNTHETIC", "PRODUCTION"}
_ID_RE = re.compile(r"^[a-z][a-z0-9._:-]{0,127}$")


def _fail(code: str, path: str, message: str) -> None:
    raise ArtifactError(code, path, message)


def _id(value: Any, path: str) -> str:
    if type(value) is not str or not _ID_RE.fullmatch(value):
        _fail("E_ANALYSIS_ID", path, "lowercase logical id required")
    return value


def _items(values: Any, field: str, *, kind: str) -> list[Dict[str, Any]]:
    if not isinstance(values, (list, tuple)):
        _fail("E_ANALYSIS_SCHEMA", field, "array required")
    result = []
    seen = set()
    for index, value in enumerate(values):
        path = f"{field}/{index}"
        if not isinstance(value, Mapping):
            _fail("E_ANALYSIS_SCHEMA", path, "object required")
        allowed = {"id", "statement", "source_anchors", "confidence", "reason"}
        if set(value) - allowed or {"id", "statement"} - set(value):
            _fail("E_ANALYSIS_SCHEMA", path, "closed analysis item required")
        item_id = _id(value["id"], f"{path}/id")
        if item_id in seen:
            _fail("E_ANALYSIS_DUPLICATE", f"{field}/{index}/id", "duplicate item id")
        seen.add(item_id)
        if type(value["statement"]) is not str or not value["statement"].strip():
            _fail("E_ANALYSIS_SCHEMA", f"{path}/statement", "non-empty statement required")
        normalized: Dict[str, Any] = {"id": item_id, "statement": value["statement"]}
        if "reason" in value:
            if type(value["reason"]) is not str or not value["reason"].strip():
                _fail("E_ANALYSIS_SCHEMA", f"{path}/reason", "reason must be non-empty text")
            normalized["reason"] = value["reason"]
        if "confidence" in value:
            confidence = value["confidence"]
            if type(confidence) is not str or confidence not in {"high", "medium", "low", "unknown"}:
                _fail("E_ANALYSIS_SCHEMA", f"{path}/confidence", "unsupported confidence")
            normalized["confidence"] = confidence
        anchors = value.get("source_anchors", [])
        if not isinstance(anchors, list):
            _fail("E_ANALYSIS_SOURCE", f"{path}/source_anchors", "array required")
        normalized["source_anchors"] = []
        for anchor_index, anchor in enumerate(anchors):
            try:
                normalized["source_anchors"].append(source_anchor(anchor))
            except ArtifactError as exc:
                _fail(exc.code, f"{path}/source_anchors/{anchor_index}", str(exc))
        result.append(normalized)
    return result


def build_analysis_report(*, artifact_id: str, producer: Mapping[str, Any], source_refs: Sequence[Mapping[str, Any]],
                          candidate_ref: Optional[Mapping[str, Any]], environment_ref: Optional[Mapping[str, Any]],
                          facts: Sequence[Mapping[str, Any]], inferences: Sequence[Mapping[str, Any]] = (),
                          assumptions: Sequence[Mapping[str, Any]] = (), questions: Sequence[Mapping[str, Any]] = (),
                          status: str = "DRAFT_VALIDATED", evidence_class: str = "OFFLINE_FIXTURE",
                          check_set_ref: Optional[Mapping[str, Any]] = None, analysis_mode: str = "offline") -> Dict[str, Any]:
    """Build and validate one deterministic AnalysisReport envelope."""
    if type(artifact_id) is not str or not artifact_id:
        _fail("E_ANALYSIS_SCHEMA", "/artifact_id", "non-empty artifact id required")
    if type(status) is not str or status not in ANALYSIS_STATUSES:
        _fail("E_ANALYSIS_STATUS", "/status", "analysis cannot claim a production PASS")
    if type(evidence_class) is not str or evidence_class not in EVIDENCE_CLASSES:
        _fail("E_ANALYSIS_EVIDENCE", "/payload/evidence_class", "unknown evidence class")
    if type(analysis_mode) is not str or analysis_mode not in {"offline", "local_reference", "production"}:
        _fail("E_ANALYSIS_MODE", "/payload/analysis_mode", "unsupported analysis mode")
    if analysis_mode != "production" and evidence_class == "PRODUCTION":
        _fail("E_ANALYSIS_EVIDENCE", "/payload/evidence_class", "offline analysis cannot use production evidence")
    if status == "READY" and evidence_class in {"OFFLINE_FIXTURE", "SYNTHETIC"}:
        _fail("E_ANALYSIS_STATUS", "/status", "synthetic evidence cannot be ready for production")
    if not isinstance(source_refs, Sequence) or isinstance(source_refs, (str, bytes)):
        _fail("E_ANALYSIS_SOURCE", "/source_refs", "source refs sequence required")
    refs = [resource_ref(item, f"/source_refs/{index}") for index, item in enumerate(source_refs)]
    if check_set_ref is not None:
        check_set_ref = resource_ref(check_set_ref, "/payload/check_set_ref")
    payload = {
        "analysis_mode": analysis_mode,
        "evidence_class": evidence_class,
        "facts": _items(facts, "/payload/facts", kind="fact"),
        "inferences": _items(inferences, "/payload/inferences", kind="inference"),
        "assumptions": _items(assumptions, "/payload/assumptions", kind="assumption"),
        "questions": _items(questions, "/payload/questions", kind="question"),
        "check_set_ref": check_set_ref,
    }
    record = {"record_type": ANALYSIS_RECORD_TYPE, "schema_version": 1, "artifact_id": artifact_id,
              "producer": copy.deepcopy(dict(producer)), "status": status, "source_refs": refs,
              "candidate_ref": None if candidate_ref is None else resource_ref(candidate_ref, "/candidate_ref"),
              "environment_ref": None if environment_ref is None else resource_ref(environment_ref, "/environment_ref"),
              "payload": payload}
    return validate_analysis_report(record)


def validate_analysis_report(record: Mapping[str, Any]) -> Dict[str, Any]:
    normalized = validate_artifact(record)
    if normalized["record_type"] != ANALYSIS_RECORD_TYPE:
        _fail("E_ANALYSIS_SCHEMA", "/record_type", "analysis-report required")
    if type(normalized["status"]) is not str or normalized["status"] not in ANALYSIS_STATUSES:
        _fail("E_ANALYSIS_STATUS", "/status", "analysis status is not offline-safe")
    payload = normalized["payload"]
    required = {"analysis_mode", "evidence_class", "facts", "inferences", "assumptions", "questions", "check_set_ref"}
    if set(payload) != required:
        _fail("E_ANALYSIS_SCHEMA", "/payload", "closed analysis payload required")
    if type(payload["analysis_mode"]) is not str or payload["analysis_mode"] not in {"offline", "local_reference", "production"}:
        _fail("E_ANALYSIS_MODE", "/payload/analysis_mode", "unsupported analysis mode")
    if type(payload["evidence_class"]) is not str or payload["evidence_class"] not in EVIDENCE_CLASSES:
        _fail("E_ANALYSIS_EVIDENCE", "/payload/evidence_class", "unknown evidence class")
    for name in ("facts", "inferences", "assumptions", "questions"):
        payload[name] = _items(payload[name], f"/payload/{name}", kind=name[:-1])
    if payload["check_set_ref"] is not None:
        payload["check_set_ref"] = resource_ref(payload["check_set_ref"], "/payload/check_set_ref")
    if payload["analysis_mode"] != "production" and payload["evidence_class"] == "PRODUCTION":
        _fail("E_ANALYSIS_EVIDENCE", "/payload/evidence_class", "production evidence requires production mode")
    declared = {(ref["kind"], ref["id"], ref["path"], ref["sha256"]) for ref in normalized["source_refs"]}
    for group in ("facts", "inferences", "assumptions", "questions"):
        for item_index, item in enumerate(payload[group]):
            for anchor_index, anchor in enumerate(item["source_anchors"]):
                ref = anchor["ref"]
                if (ref["kind"], ref["id"], ref["path"], ref["sha256"]) not in declared:
                    _fail("E_ANALYSIS_PROVENANCE", f"/payload/{group}/{item_index}/source_anchors/{anchor_index}/ref", "anchor reference is not declared in source_refs")
    return normalized


def assert_analysis_current(record: Mapping[str, Any], *, candidate_ref: Optional[Mapping[str, Any]],
                            source_refs: Sequence[Mapping[str, Any]], environment_ref: Optional[Mapping[str, Any]],
                            check_set_ref: Optional[Mapping[str, Any]] = None) -> None:
    """Reject reuse when any provenance binding differs from the expected input."""
    current = validate_analysis_report(record)
    expected_candidate = None if candidate_ref is None else resource_ref(candidate_ref, "/candidate_ref")
    expected_environment = None if environment_ref is None else resource_ref(environment_ref, "/environment_ref")
    expected_sources = [resource_ref(item, f"/source_refs/{index}") for index, item in enumerate(source_refs)]
    if current["candidate_ref"] != expected_candidate:
        _fail("E_ANALYSIS_DRIFT", "/candidate_ref", "candidate binding changed")
    if current["environment_ref"] != expected_environment:
        _fail("E_ANALYSIS_DRIFT", "/environment_ref", "environment binding changed")
    if current["source_refs"] != expected_sources:
        _fail("E_ANALYSIS_DRIFT", "/source_refs", "source binding changed")
    expected_check = None if check_set_ref is None else resource_ref(check_set_ref, "/payload/check_set_ref")
    if current["payload"]["check_set_ref"] != expected_check:
        _fail("E_ANALYSIS_DRIFT", "/payload/check_set_ref", "check set binding changed")


__all__ = ["ANALYSIS_RECORD_TYPE", "build_analysis_report", "validate_analysis_report", "assert_analysis_current"]
