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
    execution_id = check_execution_id(check_plan_id=check_plan_id, candidate_digest=candidate_digest,
                                      environment_digest=environment_digest)
    if dispatcher_connected and dispatcher_receipt is None:
        _err("E_CHECK_RECEIPT", "dispatcher receipt is required for a production status")
    if dispatcher_receipt is not None:
        required = {"check_execution_id", "check_plan_id", "candidate_digest", "environment_digest", "status"}
        if set(dispatcher_receipt) != required:
            _err("E_CHECK_RECEIPT", "closed dispatcher receipt required")
        if dispatcher_receipt["check_execution_id"] != execution_id or dispatcher_receipt["check_plan_id"] != check_plan_id or dispatcher_receipt["candidate_digest"] != candidate_digest or dispatcher_receipt["environment_digest"] != environment_digest or dispatcher_receipt["status"] != status:
            _err("E_CHECK_RECEIPT", "receipt identity does not match the requested check")
        dispatcher_connected = True
    if not dispatcher_connected:
        status = "REFERENCE_ONLY" if status in {"PASS", "FAIL"} else status
    evidence = {"execution_mode": "deterministic_check", "check_execution_id": execution_id,
                "check_plan_id": check_plan_id, "candidate_digest": candidate_digest,
                "environment_digest": environment_digest, "status": status,
                "output_digest": output_digest, "reason": reason}
    if dispatcher_receipt is not None:
        evidence["dispatcher_receipt"] = deepcopy(dict(dispatcher_receipt))
    if status == "REFERENCE_ONLY" and not reason:
        evidence["reason"] = "dispatcher_not_connected"
    return evidence


def build_check_artifact(*, artifact_id: str, producer: Mapping[str, str], candidate_ref: Mapping[str, str] | None,
                         environment_ref: Mapping[str, str] | None, source_refs: Sequence[Mapping[str, str]],
                         plan: Mapping[str, Any], evidence: Mapping[str, Any]) -> dict[str, Any]:
    if evidence.get("execution_mode") != "deterministic_check" or not evidence.get("check_execution_id"):
        _err("E_CHECK_EVIDENCE", "deterministic check evidence required")
    status = evidence["status"]
    if status not in {"PASS", "FAIL", "BLOCKED", "NOT_RUN", "UNKNOWN", "REFERENCE_ONLY"}:
        _err("E_CHECK_EVIDENCE", "invalid evidence status")
    if status == "PASS":
        required = {"check_execution_id", "check_plan_id", "candidate_digest", "environment_digest", "status"}
        receipt = evidence.get("dispatcher_receipt")
        if not isinstance(receipt, Mapping) or set(receipt) != required:
            _err("E_CHECK_EVIDENCE", "PASS requires a closed dispatcher receipt")
    return validate_artifact({"record_type": "check-plan", "schema_version": 1, "artifact_id": artifact_id,
      "producer": dict(producer), "status": status, "source_refs": list(source_refs),
      "candidate_ref": candidate_ref, "environment_ref": environment_ref,
      "payload": {"plan": deepcopy(dict(plan)), "evidence": deepcopy(dict(evidence))}})

__all__ = ["build_check_artifact", "check_execution_id", "make_check_evidence"]
