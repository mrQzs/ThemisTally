"""Fixed content oracle and review readiness helpers for offline docs checks."""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence, Set

from .builtin_artifacts import ArtifactError, digest, validate_artifact


@dataclass(frozen=True)
class CheckBinding(object):
    candidate_sha256: str
    check_set_sha256: str
    environment_sha256: str

    def __post_init__(self):
        for name in ("candidate_sha256", "check_set_sha256", "environment_sha256"):
            value = getattr(self, name)
            if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                raise ArtifactError("E_BINDING_HASH", "/" + name, "lowercase SHA-256 required")


def content_oracle(document: Any, expected_text: str, *, encoding: str = "utf-8", document_sha256: Optional[str] = None) -> dict:
    """Compare one fixed expected sentence; no model or semantic inference."""
    if not isinstance(expected_text, str) or not expected_text:
        raise ArtifactError("E_CONTENT_ORACLE", "/expected_text", "fixed expected text required")
    if isinstance(document, bytes):
        try:
            text = document.decode(encoding)
        except (LookupError, UnicodeDecodeError) as exc:
            raise ArtifactError("E_CONTENT_ENCODING", "/document", "document encoding unavailable") from exc
        actual_sha256 = digest(document)
    elif isinstance(document, str):
        text, actual_sha256 = document, digest(document.encode(encoding))
    else:
        raise ArtifactError("E_CONTENT_ORACLE", "/document", "bytes or text required")
    if document_sha256 is not None and document_sha256 != actual_sha256:
        return {"status": "UNKNOWN", "reason": "DOCUMENT_DRIFT", "document_sha256": actual_sha256}
    return {"status": "REVIEWED_SATISFIED" if expected_text in text else "CONTENT_MISMATCH", "expected_sha256": digest(expected_text.encode("utf-8")), "document_sha256": actual_sha256, "match_count": text.count(expected_text), "oracle": "fixed-substring-v1"}


def quality_issues(observation: Mapping[str, Any], required_tests: Set[str]) -> list:
    issues = []
    if observation.get("transport_complete") is not True:
        issues.append("E_CHECK_INCOMPLETE")
    if type(observation.get("exit_code")) is not int or observation.get("exit_code") != 0:
        issues.append("E_CHECK_EXIT")
    tests = observation.get("tests", {})
    if not isinstance(tests, Mapping) or not tests:
        issues.append("E_NO_TESTS")
    missing = sorted(required_tests - set(tests))
    if missing:
        issues.append("E_TARGET_TEST_MISSING")
    for ident in sorted(required_tests & set(tests)):
        row = tests[ident]
        if not isinstance(row, Mapping) or row.get("status") != "PASSED":
            issues.append("E_TARGET_NOT_PASSED:" + ident)
    if isinstance(tests, Mapping) and any(isinstance(row, Mapping) and row.get("status") in {"ASSERTION_FAILURE", "ERROR", "XPASS"} for row in tests.values()):
        issues.append("E_TEST_SUITE_FAILURE")
    return issues


def review_readiness(expected: CheckBinding, observations: Sequence[Mapping[str, Any]], required_check_ids: Set[str], required_tests: Set[str], content_status: str, core_gates: str) -> dict:
    issues = []
    ids = [o.get("check_id") for o in observations]
    if len(ids) != len(set(ids)):
        issues.append("E_CHECK_DUPLICATE")
    if set(ids) != set(required_check_ids):
        issues.append("E_CHECK_SET")
    binding = {"candidate_sha256": expected.candidate_sha256, "check_set_sha256": expected.check_set_sha256, "environment_sha256": expected.environment_sha256}
    for observation in observations:
        if observation.get("binding") != binding:
            issues.append("E_CANDIDATE_OR_ENV_DRIFT")
        if observation.get("source_kind") != "core_observation":
            issues.append("E_SELF_REPORT")
        issues.extend(quality_issues(observation, required_tests))
    if content_status != "REVIEWED_SATISFIED":
        issues.append("E_CONTENT_REVIEW_REQUIRED")
    if core_gates != "SATISFIED":
        issues.append("E_CORE_GATES")
    return {"status": "BLOCKED" if issues else "READY_FOR_SUPERVISOR_DECISION", "issues": sorted(set(issues))}


def build_review_bundle(*, docs_check: Mapping[str, Any], content_review: Mapping[str, Any], observations: Sequence[Mapping[str, Any]], readiness: Mapping[str, Any], source_refs: Sequence[Mapping[str, str]] = (), candidate_ref: Optional[Mapping[str, str]] = None, environment_ref: Optional[Mapping[str, str]] = None, artifact_id: str = "review-bundle", status: Optional[str] = None) -> dict:
    """Assemble a review-bundle; never promotes readiness to a core verdict."""
    if not isinstance(docs_check, Mapping) or docs_check.get("record_type") != "docs-check":
        raise ArtifactError("E_REVIEW_INPUT", "/docs_check", "validated docs-check artifact required")
    docs_check = validate_artifact(docs_check)
    if not isinstance(content_review, Mapping) or content_review.get("status") not in {"REVIEWED_SATISFIED", "CONTENT_MISMATCH", "UNKNOWN"}:
        raise ArtifactError("E_REVIEW_INPUT", "/content_review", "fixed oracle result required")
    payload = {"docs_check": copy.deepcopy(dict(docs_check)), "content_review": copy.deepcopy(dict(content_review)), "observations": copy.deepcopy(list(observations)), "readiness": copy.deepcopy(dict(readiness)), "semantic_review": "FIXED_ORACLE_ONLY"}
    if status is None:
        status = "READY" if readiness.get("status") == "READY_FOR_SUPERVISOR_DECISION" else "BLOCKED"
    record = {"record_type": "review-bundle", "schema_version": 1, "artifact_id": artifact_id, "producer": {"kind": "builtin-plugin", "id": "docs-review-oracle", "version": "1.0.0"}, "status": status, "source_refs": [dict(x) for x in source_refs], "candidate_ref": None if candidate_ref is None else dict(candidate_ref), "environment_ref": None if environment_ref is None else dict(environment_ref), "payload": payload}
    return validate_artifact(record)


__all__ = ["CheckBinding", "content_oracle", "quality_issues", "review_readiness", "build_review_bundle"]
