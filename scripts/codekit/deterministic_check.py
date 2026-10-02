"""Deterministic check evidence boundary for built-in plugins.

The evidence is reference-only until a trusted dispatcher supplies an execution
record.  This module computes stable IDs and refuses to imply production run.
"""
from __future__ import annotations
import hashlib, json
from copy import deepcopy
from typing import Any, Mapping, Sequence
from .builtin_artifacts import ArtifactError, canonical_bytes, validate_artifact


def _err(code: str, message: str) -> None:
    raise ArtifactError(code, "/check", message)


def check_execution_id(*, check_plan_id: str, candidate_digest: str, environment_digest: str) -> str:
    if any(type(x) is not str or not x for x in (check_plan_id, candidate_digest, environment_digest)):
        _err("E_CHECK_ID", "check plan, candidate and environment identifiers required")
    raw = canonical_bytes({"check_plan_id": check_plan_id, "candidate_digest": candidate_digest,
                           "environment_digest": environment_digest})
    return hashlib.sha256(raw).hexdigest()


def make_check_evidence(*, check_plan_id: str, candidate_digest: str, environment_digest: str,
                        status: str, dispatcher_connected: bool = False,
                        output_digest: str | None = None, reason: str | None = None,
                        dispatcher_receipt: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if status not in {"PASS", "FAIL", "BLOCKED", "NOT_RUN", "UNKNOWN"}:
        _err("E_CHECK_STATUS", "unsupported check status")
    if type(dispatcher_connected) is not bool:
        _err("E_CHECK_RECEIPT", "dispatcher_connected must be boolean")
    if output_digest is not None and (type(output_digest) is not str or not output_digest or len(output_digest) > 256):
        _err("E_CHECK_EVIDENCE", "output digest must be bounded text")
    if reason is not None and (type(reason) is not str or not reason or len(reason) > 4096):
        _err("E_CHECK_EVIDENCE", "reason must be bounded text")
    execution_id = check_execution_id(check_plan_id=check_plan_id, candidate_digest=candidate_digest,
                                      environment_digest=environment_digest)
    if dispatcher_connected and dispatcher_receipt is None:
        _err("E_CHECK_RECEIPT", "dispatcher receipt is required for a production status")
    if dispatcher_receipt is not None:
        required = {"check_execution_id", "check_plan_id", "candidate_digest", "environment_digest", "status"}
        if not isinstance(dispatcher_receipt, Mapping) or set(dispatcher_receipt) != required or any(type(dispatcher_receipt[field]) is not str or not dispatcher_receipt[field] for field in required - {"status"}):
            _err("E_CHECK_RECEIPT", "closed dispatcher receipt required")
        if dispatcher_receipt["check_execution_id"] != execution_id or dispatcher_receipt["check_plan_id"] != check_plan_id or dispatcher_receipt["candidate_digest"] != candidate_digest or dispatcher_receipt["environment_digest"] != environment_digest or dispatcher_receipt["status"] != status:
            _err("E_CHECK_RECEIPT", "receipt identity does not match the requested check")
        dispatcher_connected = True
    observed_status = status
    # A caller-supplied mapping is not proof of dispatcher registration.
    # There is no trusted dispatcher connector in this offline module.
    status = "REFERENCE_ONLY" if status in {"PASS", "FAIL"} else status
    evidence = {"execution_mode": "deterministic_check", "check_execution_id": execution_id,
                "check_plan_id": check_plan_id, "candidate_digest": candidate_digest,
                "environment_digest": environment_digest, "status": status,
                "observed_status": observed_status,
                "output_digest": output_digest, "reason": reason}
    if dispatcher_receipt is not None:
        evidence["dispatcher_receipt"] = deepcopy(dict(dispatcher_receipt))
    if status == "REFERENCE_ONLY" and not reason:
        evidence["reason"] = "dispatcher_not_verified"
    return evidence


def build_check_artifact(*, artifact_id: str, producer: Mapping[str, str], candidate_ref: Mapping[str, str] | None,
                         environment_ref: Mapping[str, str] | None, source_refs: Sequence[Mapping[str, str]],
                         plan: Mapping[str, Any], evidence: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(plan, Mapping):
        _err("E_CHECK_PLAN", "check plan mapping required")
    if not isinstance(source_refs, Sequence) or isinstance(source_refs, (str, bytes)):
        _err("E_CHECK_EVIDENCE", "source refs sequence required")
    base_evidence_fields = {"execution_mode", "check_execution_id", "check_plan_id", "candidate_digest",
                            "environment_digest", "status", "observed_status", "output_digest", "reason"}
    evidence_fields = set(evidence) if isinstance(evidence, Mapping) else set()
    if not isinstance(evidence, Mapping) or evidence_fields not in (base_evidence_fields, base_evidence_fields | {"dispatcher_receipt"}):
        _err("E_CHECK_EVIDENCE", "closed deterministic check evidence required")
    if evidence.get("execution_mode") != "deterministic_check" or any(
            type(evidence.get(field)) is not str or not evidence[field]
            for field in ("check_execution_id", "check_plan_id", "candidate_digest", "environment_digest")):
        _err("E_CHECK_EVIDENCE", "deterministic check evidence required")
    status = evidence["status"]
    if status not in {"PASS", "FAIL", "BLOCKED", "NOT_RUN", "UNKNOWN", "REFERENCE_ONLY"}:
        _err("E_CHECK_EVIDENCE", "invalid evidence status")
    required = {"check_execution_id", "check_plan_id", "candidate_digest", "environment_digest", "status"}
    if not required.issubset(evidence):
        _err("E_CHECK_EVIDENCE", "complete execution identity required")
    actual_id = check_execution_id(check_plan_id=evidence["check_plan_id"], candidate_digest=evidence["candidate_digest"],
                                   environment_digest=evidence["environment_digest"])
    if actual_id != evidence["check_execution_id"]:
        _err("E_CHECK_EVIDENCE", "execution identity does not match evidence")
    receipt = evidence.get("dispatcher_receipt")
    if receipt is not None:
        if not isinstance(receipt, Mapping) or set(receipt) != required:
            _err("E_CHECK_EVIDENCE", "closed dispatcher receipt required")
        if any(receipt[field] != evidence[field] for field in required - {"status"}) or receipt["status"] != evidence.get("observed_status", status):
            _err("E_CHECK_EVIDENCE", "dispatcher receipt identity does not match evidence")
    for ref, field in ((candidate_ref, "candidate_digest"), (environment_ref, "environment_digest")):
        if ref is not None and ref.get("sha256") != evidence[field]:
            _err("E_CHECK_EVIDENCE", "artifact binding differs from check evidence")
    observed = evidence.get("observed_status", status)
    if observed not in {"PASS", "FAIL", "BLOCKED", "NOT_RUN", "UNKNOWN"}:
        _err("E_CHECK_EVIDENCE", "observed check status required")
    for field in ("output_digest", "reason"):
        value = evidence.get(field)
        if value is not None and (type(value) is not str or not value or len(value) > (256 if field == "output_digest" else 4096)):
            _err("E_CHECK_EVIDENCE", f"{field} must be bounded text or null")
    expected_status = "REFERENCE_ONLY" if observed in {"PASS", "FAIL"} else observed
    if status not in {observed, expected_status}:
        _err("E_CHECK_EVIDENCE", "evidence status differs from observed status")
    status = expected_status
    evidence = {**deepcopy(dict(evidence)), "status": status, "observed_status": observed}
    return validate_artifact({"record_type": "check-plan", "schema_version": 1, "artifact_id": artifact_id,
      "producer": dict(producer), "status": status, "source_refs": list(source_refs),
      "candidate_ref": candidate_ref, "environment_ref": environment_ref,
      "payload": {"plan": deepcopy(dict(plan)), "evidence": deepcopy(dict(evidence))}})

__all__ = ["build_check_artifact", "check_execution_id", "make_check_evidence"]
