"""Fixed content oracle and review readiness helpers for offline docs checks."""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence, Set

from .builtin_artifacts import ArtifactError, digest, validate_artifact
from .builtin_docs_checks import validate_docs_check


_OBSERVATION_FIELDS = frozenset({
    "check_id", "binding", "source_kind", "transport_complete", "exit_code", "tests",
})
_BINDING_FIELDS = frozenset({"candidate_sha256", "check_set_sha256", "environment_sha256"})
_TEST_STATUSES = frozenset({"PASSED", "ASSERTION_FAILURE", "ERROR", "SKIPPED", "XFAIL", "XPASS"})
_MAX_COLLECTION = 1000
_MAX_TEXT = 4096


def _invalid(code: str, path: str, message: str) -> None:
    raise ArtifactError(code, path, message)


def _text(value: Any, path: str) -> str:
    if type(value) is not str or not value or len(value) > _MAX_TEXT or any(ord(char) < 32 for char in value):
        _invalid("E_CHECK_SCHEMA", path, "bounded non-empty text required")
    return value


def _name_set(value: Any, path: str) -> set[str]:
    if not isinstance(value, (set, frozenset)):
        _invalid("E_CHECK_SET", path, "set of check IDs required")
    if len(value) > _MAX_COLLECTION:
        _invalid("E_CHECK_SET", path, "check ID set exceeds limit")
    result: set[str] = set()
    for index, item in enumerate(value):
        if type(item) is not str or not item or len(item) > _MAX_TEXT or any(ord(char) < 32 for char in item):
            _invalid("E_CHECK_SET", f"{path}/{index}", "bounded check ID text required")
        result.add(item)
    return result


def _binding(value: Any, path: str) -> dict[str, str]:
    if not isinstance(value, Mapping) or set(value) != _BINDING_FIELDS:
        _invalid("E_CHECK_BINDING", path, "closed check binding required")
    normalized: dict[str, str] = {}
    for name in sorted(_BINDING_FIELDS):
        item = value[name]
        if type(item) is not str or len(item) != 64 or any(char not in "0123456789abcdef" for char in item):
            _invalid("E_CHECK_BINDING", f"{path}/{name}", "lowercase SHA-256 required")
        normalized[name] = item
    return normalized


def _observation(value: Any, path: str = "/observation") -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _OBSERVATION_FIELDS:
        _invalid("E_CHECK_OBSERVATION", path, "closed check observation required")
    _text(value["check_id"], f"{path}/check_id")
    _binding(value["binding"], f"{path}/binding")
    _text(value["source_kind"], f"{path}/source_kind")
    if type(value["transport_complete"]) is not bool:
        _invalid("E_CHECK_OBSERVATION", f"{path}/transport_complete", "boolean required")
    if value["exit_code"] is not None and type(value["exit_code"]) is not int:
        _invalid("E_CHECK_OBSERVATION", f"{path}/exit_code", "integer or null required")
    tests = value["tests"]
    if not isinstance(tests, Mapping):
        _invalid("E_CHECK_OBSERVATION", f"{path}/tests", "test result map required")
    if len(tests) > _MAX_COLLECTION:
        _invalid("E_CHECK_OBSERVATION", f"{path}/tests", "test result map exceeds limit")
    for ident, row in tests.items():
        _text(ident, f"{path}/tests/id")
        if not isinstance(row, Mapping) or set(row) - {"status", "assertion_id"} or "status" not in row:
            _invalid("E_CHECK_OBSERVATION", f"{path}/tests/{ident}", "closed test result required")
        if type(row["status"]) is not str or row["status"] not in _TEST_STATUSES:
            _invalid("E_CHECK_OBSERVATION", f"{path}/tests/{ident}/status", "unsupported test status")
        if "assertion_id" in row and row["assertion_id"] is not None:
            _text(row["assertion_id"], f"{path}/tests/{ident}/assertion_id")
    return value


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
    if type(encoding) is not str or not encoding:
        raise ArtifactError("E_CONTENT_ENCODING", "/encoding", "encoding name required")
    if document_sha256 is not None and (type(document_sha256) is not str or len(document_sha256) != 64 or any(char not in "0123456789abcdef" for char in document_sha256)):
        raise ArtifactError("E_CONTENT_ORACLE", "/document_sha256", "lowercase SHA-256 required")
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
    observation = _observation(observation)
    required = _name_set(required_tests, "/required_tests")
    issues = []
    if observation.get("transport_complete") is not True:
        issues.append("E_CHECK_INCOMPLETE")
    if type(observation.get("exit_code")) is not int or observation.get("exit_code") != 0:
        issues.append("E_CHECK_EXIT")
    tests = observation.get("tests", {})
    if not isinstance(tests, Mapping) or not tests:
        issues.append("E_NO_TESTS")
    missing = sorted(required - set(tests))
    if missing:
        issues.append("E_TARGET_TEST_MISSING")
    for ident in sorted(required & set(tests)):
        row = tests[ident]
        if not isinstance(row, Mapping) or row.get("status") != "PASSED":
            issues.append("E_TARGET_NOT_PASSED:" + ident)
    if isinstance(tests, Mapping) and any(isinstance(row, Mapping) and row.get("status") in {"ASSERTION_FAILURE", "ERROR", "XPASS"} for row in tests.values()):
        issues.append("E_TEST_SUITE_FAILURE")
    return issues


def review_readiness(expected: CheckBinding, observations: Sequence[Mapping[str, Any]], required_check_ids: Set[str], required_tests: Set[str], content_status: str, core_gates: str) -> dict:
    if not isinstance(expected, CheckBinding):
        _invalid("E_CHECK_BINDING", "/expected", "CheckBinding required")
    required_ids = _name_set(required_check_ids, "/required_check_ids")
    required = _name_set(required_tests, "/required_tests")
    if not isinstance(observations, (list, tuple)) or len(observations) > _MAX_COLLECTION:
        _invalid("E_CHECK_OBSERVATION", "/observations", "bounded observation sequence required")
    normalized_observations = [_observation(observation, f"/observations/{index}") for index, observation in enumerate(observations)]
    _text(content_status, "/content_status")
    _text(core_gates, "/core_gates")
    issues = []
    ids = [o["check_id"] for o in normalized_observations]
    if len(ids) != len(set(ids)):
        issues.append("E_CHECK_DUPLICATE")
    if set(ids) != required_ids:
        issues.append("E_CHECK_SET")
    binding = {"candidate_sha256": expected.candidate_sha256, "check_set_sha256": expected.check_set_sha256, "environment_sha256": expected.environment_sha256}
    for observation in normalized_observations:
        if observation.get("binding") != binding:
            issues.append("E_CANDIDATE_OR_ENV_DRIFT")
        if observation.get("source_kind") != "core_observation":
            issues.append("E_SELF_REPORT")
        issues.extend(quality_issues(observation, required))
    if content_status != "REVIEWED_SATISFIED":
        issues.append("E_CONTENT_REVIEW_REQUIRED")
    if core_gates != "SATISFIED":
        issues.append("E_CORE_GATES")
    return {"status": "BLOCKED" if issues else "READY_FOR_SUPERVISOR_DECISION", "issues": sorted(set(issues))}


def build_review_bundle(*, docs_check: Mapping[str, Any], content_review: Mapping[str, Any], observations: Sequence[Mapping[str, Any]], readiness: Mapping[str, Any], source_refs: Sequence[Mapping[str, str]] = (), candidate_ref: Optional[Mapping[str, str]] = None, environment_ref: Optional[Mapping[str, str]] = None, artifact_id: str = "review-bundle", status: Optional[str] = None) -> dict:
    """Assemble a review-bundle; never promotes readiness to a core verdict."""
    if status is not None and type(status) is not str:
        raise ArtifactError("E_REVIEW_INPUT", "/status", "status must be text or null")
    if status == "PASS":
        raise ArtifactError("E_REVIEW_PRODUCTION_GATE", "/status", "PASS requires a trusted dispatcher verdict")
    if not isinstance(docs_check, Mapping) or docs_check.get("record_type") != "docs-check":
        raise ArtifactError("E_REVIEW_INPUT", "/docs_check", "validated docs-check artifact required")
    docs_check = validate_docs_check(docs_check)
    if not isinstance(content_review, Mapping) or type(content_review.get("status")) is not str or content_review.get("status") not in {"REVIEWED_SATISFIED", "CONTENT_MISMATCH", "UNKNOWN"}:
        raise ArtifactError("E_REVIEW_INPUT", "/content_review", "fixed oracle result required")
    if not isinstance(observations, Sequence) or isinstance(observations, (str, bytes)):
        raise ArtifactError("E_REVIEW_INPUT", "/observations", "observation sequence required")
    if not isinstance(readiness, Mapping):
        raise ArtifactError("E_REVIEW_INPUT", "/readiness", "readiness mapping required")
    if set(readiness) != {"status", "issues"}:
        raise ArtifactError("E_REVIEW_INPUT", "/readiness", "closed readiness result required")
    if readiness["status"] not in {"BLOCKED", "READY_FOR_SUPERVISOR_DECISION"}:
        raise ArtifactError("E_REVIEW_INPUT", "/readiness/status", "unsupported readiness status")
    if not isinstance(readiness["issues"], list) or any(type(issue) is not str or not issue for issue in readiness["issues"]):
        raise ArtifactError("E_REVIEW_INPUT", "/readiness/issues", "readiness issue list required")
    checked_observations = [_observation(observation, f"/observations/{index}") for index, observation in enumerate(observations)]
    if readiness["status"] == "READY_FOR_SUPERVISOR_DECISION":
        if readiness["issues"] or not checked_observations or content_review["status"] != "REVIEWED_SATISFIED":
            raise ArtifactError("E_REVIEW_BINDING", "/readiness", "ready result is inconsistent with review inputs")
        bindings = {tuple(sorted(observation["binding"].items())) for observation in checked_observations}
        if len(bindings) != 1 or any(
            observation["source_kind"] != "core_observation"
            or observation["transport_complete"] is not True
            or observation["exit_code"] != 0
            or not observation["tests"]
            or any(row.get("status") != "PASSED" for row in observation["tests"].values())
            for observation in checked_observations
        ):
            raise ArtifactError("E_REVIEW_BINDING", "/readiness", "ready result is inconsistent with observations")
    if not isinstance(source_refs, Sequence) or isinstance(source_refs, (str, bytes)):
        raise ArtifactError("E_REVIEW_INPUT", "/source_refs", "source refs sequence required")
    payload = {"docs_check": copy.deepcopy(dict(docs_check)), "content_review": copy.deepcopy(dict(content_review)), "observations": copy.deepcopy(list(checked_observations)), "readiness": copy.deepcopy(dict(readiness)), "semantic_review": "FIXED_ORACLE_ONLY"}
    if status is None:
        status = "READY" if readiness.get("status") == "READY_FOR_SUPERVISOR_DECISION" else "BLOCKED"
    record = {"record_type": "review-bundle", "schema_version": 1, "artifact_id": artifact_id, "producer": {"kind": "builtin-plugin", "id": "docs-review-oracle", "version": "1.0.0"}, "status": status, "source_refs": [dict(x) for x in source_refs], "candidate_ref": None if candidate_ref is None else dict(candidate_ref), "environment_ref": None if environment_ref is None else dict(environment_ref), "payload": payload}
    return validate_artifact(record)


__all__ = ["CheckBinding", "content_oracle", "quality_issues", "review_readiness", "build_review_bundle"]
