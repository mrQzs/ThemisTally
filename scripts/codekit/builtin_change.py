"""Deterministic, provenance-bound ``code-change`` report validation."""

from __future__ import annotations

import copy
import fnmatch
import re
from typing import Any, Dict, Mapping, Optional, Sequence

from .builtin_artifacts import ArtifactError, resource_ref, validate_artifact


CHANGE_RECORD_TYPE = "change-report"
CHANGE_STATUSES = {"DRAFT_VALIDATED", "READY", "UNKNOWN", "BLOCKED", "NOT_RUN", "REFERENCE_ONLY"}
EVIDENCE_CLASSES = {"OFFLINE_FIXTURE", "LOCAL_REFERENCE", "SYNTHETIC", "PRODUCTION"}
CHANGE_TYPES = {"added", "modified", "deleted", "renamed", "copied", "mode-only", "submodule"}
_SHA = re.compile(r"^[0-9a-f]{64}$")


def _fail(code: str, path: str, message: str) -> None:
    raise ArtifactError(code, path, message)


def _path(value: Any, field: str, *, allow_empty: bool = False) -> str:
    if type(value) is not str or (not value and not allow_empty):
        _fail("E_CHANGE_PATH", field, "relative path required")
    value = value.replace("\\", "/")
    parts = value.split("/")
    if (value.startswith("/") or any(part in {"", ".", ".."} for part in parts)
            or "\x00" in value or any(ord(ch) < 32 or ord(ch) == 127 for ch in value)):
        _fail("E_CHANGE_PATH", field, "unsafe relative path")
    if value.startswith("./"):
        _fail("E_CHANGE_PATH", field, "dot prefix is not canonical")
    return value


def _sha(value: Any, field: str, *, nullable: bool = False) -> Optional[str]:
    if nullable and value is None:
        return None
    if type(value) is not str or not _SHA.fullmatch(value):
        _fail("E_CHANGE_HASH", field, "lowercase SHA-256 required")
    return value


def _commit(value: Any, field: str, *, nullable: bool = False) -> Optional[str]:
    if nullable and value is None:
        return None
    if type(value) is not str or not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", value):
        _fail("E_CHANGE_SUBMODULE", field, "SHA-1 or SHA-256 commit required")
    return value


def _scope(value: Any) -> list[str]:
    if not isinstance(value, list) or not value:
        _fail("E_CHANGE_SCOPE", "/payload/scope", "non-empty scope array required")
    result = [_path(item, f"/payload/scope/{index}") for index, item in enumerate(value)]
    if len(set(result)) != len(result):
        _fail("E_CHANGE_SCOPE", "/payload/scope", "duplicate scope path")
    return sorted(result)


def _in_scope(path: str, scope: Sequence[str]) -> bool:
    for item in scope:
        if any(ch in item for ch in "*?["):
            if fnmatch.fnmatchcase(path, item):
                return True
        elif path == item or path.startswith(item.rstrip("/") + "/"):
            return True
    return False


def _files(values: Any, scope: Sequence[str]) -> list[Dict[str, Any]]:
    if not isinstance(values, list):
        _fail("E_CHANGE_SCHEMA", "/payload/files", "file array required")
    result = []
    seen = set()
    for index, value in enumerate(values):
        field = f"/payload/files/{index}"
        if not isinstance(value, Mapping):
            _fail("E_CHANGE_SCHEMA", field, "file object required")
        allowed = {"path", "old_path", "change_type", "old_sha256", "new_sha256", "old_mode", "new_mode", "submodule"}
        if set(value) - allowed or {"path", "change_type", "old_sha256", "new_sha256"} - set(value):
            _fail("E_CHANGE_SCHEMA", field, "closed changed-file object required")
        path = _path(value["path"], f"{field}/path")
        if path in seen:
            _fail("E_CHANGE_DUPLICATE", f"{field}/path", "duplicate changed path")
        seen.add(path)
        if not _in_scope(path, scope):
            _fail("E_CHANGE_SCOPE", f"{field}/path", "changed path is outside declared scope")
        change_type = value["change_type"]
        if type(change_type) is not str or change_type not in CHANGE_TYPES:
            _fail("E_CHANGE_TYPE", f"{field}/change_type", "unsupported change type")
        old_sha = _sha(value["old_sha256"], f"{field}/old_sha256", nullable=True)
        new_sha = _sha(value["new_sha256"], f"{field}/new_sha256", nullable=True)
        if change_type == "added" and (old_sha is not None or new_sha is None):
            _fail("E_CHANGE_HASH", field, "added file requires new content and no old content")
        if change_type == "deleted" and (new_sha is not None or old_sha is None):
            _fail("E_CHANGE_HASH", field, "deleted file requires old content and no new content")
        if change_type in {"modified", "mode-only", "submodule"} and old_sha is None and new_sha is None:
            _fail("E_CHANGE_HASH", field, "change requires at least one content hash")
        normalized: Dict[str, Any] = {"path": path, "change_type": change_type, "old_sha256": old_sha, "new_sha256": new_sha}
        if "old_path" in value:
            normalized["old_path"] = _path(value["old_path"], f"{field}/old_path")
            if change_type not in {"renamed", "copied"}:
                _fail("E_CHANGE_SCHEMA", f"{field}/old_path", "old_path only applies to rename/copy")
            if not _in_scope(normalized["old_path"], scope):
                _fail("E_CHANGE_SCOPE", f"{field}/old_path", "old path is outside declared scope")
        elif change_type in {"renamed", "copied"}:
            _fail("E_CHANGE_SCHEMA", field, "rename/copy requires old_path")
        for mode in ("old_mode", "new_mode"):
            if mode in value:
                if type(value[mode]) is not str or not re.fullmatch(r"[0-7]{6}", value[mode]):
                    _fail("E_CHANGE_MODE", f"{field}/{mode}", "six digit file mode required")
                normalized[mode] = value[mode]
        if "submodule" in value:
            sub = value["submodule"]
            if not isinstance(sub, Mapping) or set(sub) != {"old_commit", "new_commit", "path"}:
                _fail("E_CHANGE_SUBMODULE", f"{field}/submodule", "closed submodule binding required")
            normalized["submodule"] = {"old_commit": _commit(sub["old_commit"], f"{field}/submodule/old_commit", nullable=True),
                                        "new_commit": _commit(sub["new_commit"], f"{field}/submodule/new_commit", nullable=True),
                                        "path": _path(sub["path"], f"{field}/submodule/path")}
            if change_type != "submodule":
                _fail("E_CHANGE_SUBMODULE", f"{field}/submodule", "submodule binding requires submodule change type")
        result.append(normalized)
    return sorted(result, key=lambda item: item["path"])


def _links(value: Any) -> list[Dict[str, str]]:
    if value is None:
        return []
    if not isinstance(value, list):
        _fail("E_CHANGE_LINK", "/payload/link_bindings", "link array required")
    result = []
    seen = set()
    for index, item in enumerate(value):
        field = f"/payload/link_bindings/{index}"
        if not isinstance(item, Mapping) or set(item) != {"path", "target", "kind"}:
            _fail("E_CHANGE_LINK", field, "closed link binding required")
        path = _path(item["path"], f"{field}/path"); target = _path(item["target"], f"{field}/target")
        kind = item["kind"]
        if type(kind) is not str or kind not in {"relative", "anchor"}:
            _fail("E_CHANGE_LINK", f"{field}/kind", "only local link kinds are allowed")
        key = (path, target, kind)
        if key in seen:
            _fail("E_CHANGE_LINK", field, "duplicate link binding")
        seen.add(key); result.append({"path": path, "target": target, "kind": kind})
    return sorted(result, key=lambda item: (item["path"], item["target"], item["kind"]))


def build_change_report(*, artifact_id: str, producer: Mapping[str, Any], source_refs: Sequence[Mapping[str, Any]],
                        candidate_ref: Optional[Mapping[str, Any]], environment_ref: Optional[Mapping[str, Any]],
                        scope: Sequence[str], files: Sequence[Mapping[str, Any]], mode: str = "offline",
                        change_mode: str = "working-tree", link_bindings: Sequence[Mapping[str, Any]] = (),
                        status: str = "DRAFT_VALIDATED", evidence_class: str = "OFFLINE_FIXTURE") -> Dict[str, Any]:
    if type(artifact_id) is not str or not artifact_id:
        _fail("E_CHANGE_SCHEMA", "/artifact_id", "non-empty artifact id required")
    if type(status) is not str or status not in CHANGE_STATUSES:
        _fail("E_CHANGE_STATUS", "/status", "change report cannot claim production PASS")
    if type(evidence_class) is not str or evidence_class not in EVIDENCE_CLASSES:
        _fail("E_CHANGE_EVIDENCE", "/payload/evidence_class", "unknown evidence class")
    if type(mode) is not str or mode not in {"offline", "local_reference", "production"}:
        _fail("E_CHANGE_MODE", "/payload/mode", "unsupported mode")
    if mode != "production" and evidence_class == "PRODUCTION":
        _fail("E_CHANGE_EVIDENCE", "/payload/evidence_class", "production evidence requires production mode")
    if type(change_mode) is not str or change_mode not in {"working-tree", "commit", "patch", "unknown"}:
        _fail("E_CHANGE_MODE", "/payload/change_mode", "unsupported change mode")
    if not isinstance(scope, Sequence) or isinstance(scope, (str, bytes)):
        _fail("E_CHANGE_SCOPE", "/payload/scope", "scope sequence required")
    if not isinstance(files, Sequence) or isinstance(files, (str, bytes)):
        _fail("E_CHANGE_SCHEMA", "/payload/files", "files sequence required")
    if not isinstance(source_refs, Sequence) or isinstance(source_refs, (str, bytes)):
        _fail("E_CHANGE_SCHEMA", "/source_refs", "source refs sequence required")
    if not isinstance(link_bindings, Sequence) or isinstance(link_bindings, (str, bytes)):
        _fail("E_CHANGE_LINK", "/payload/link_bindings", "link sequence required")
    normalized_scope = _scope(list(scope)); normalized_files = _files(list(files), normalized_scope)
    payload = {"mode": mode, "evidence_class": evidence_class, "change_mode": change_mode,
               "scope": normalized_scope, "files": normalized_files, "link_bindings": _links(list(link_bindings))}
    record = {"record_type": CHANGE_RECORD_TYPE, "schema_version": 1, "artifact_id": artifact_id,
              "producer": copy.deepcopy(dict(producer)), "status": status,
              "source_refs": [resource_ref(item, f"/source_refs/{index}") for index, item in enumerate(source_refs)],
              "candidate_ref": None if candidate_ref is None else resource_ref(candidate_ref, "/candidate_ref"),
              "environment_ref": None if environment_ref is None else resource_ref(environment_ref, "/environment_ref"),
              "payload": payload}
    return validate_change_report(record)


def validate_change_report(record: Mapping[str, Any]) -> Dict[str, Any]:
    normalized = validate_artifact(record)
    if normalized["record_type"] != CHANGE_RECORD_TYPE:
        _fail("E_CHANGE_SCHEMA", "/record_type", "change-report required")
    if normalized["status"] not in CHANGE_STATUSES:
        _fail("E_CHANGE_STATUS", "/status", "unsupported offline status")
    payload = normalized["payload"]
    if set(payload) != {"mode", "evidence_class", "change_mode", "scope", "files", "link_bindings"}:
        _fail("E_CHANGE_SCHEMA", "/payload", "closed change payload required")
    if (type(payload["mode"]) is not str or payload["mode"] not in {"offline", "local_reference", "production"}
            or type(payload["evidence_class"]) is not str or payload["evidence_class"] not in EVIDENCE_CLASSES):
        _fail("E_CHANGE_SCHEMA", "/payload", "invalid mode or evidence class")
    if payload["mode"] != "production" and payload["evidence_class"] == "PRODUCTION":
        _fail("E_CHANGE_EVIDENCE", "/payload/evidence_class", "production evidence requires production mode")
    payload["scope"] = _scope(payload["scope"]); payload["files"] = _files(payload["files"], payload["scope"]); payload["link_bindings"] = _links(payload["link_bindings"])
    return normalized


def assert_change_current(record: Mapping[str, Any], *, candidate_ref: Optional[Mapping[str, Any]],
                          source_refs: Sequence[Mapping[str, Any]], environment_ref: Optional[Mapping[str, Any]]) -> None:
    current = validate_change_report(record)
    expected_candidate = None if candidate_ref is None else resource_ref(candidate_ref, "/candidate_ref")
    expected_environment = None if environment_ref is None else resource_ref(environment_ref, "/environment_ref")
    expected_sources = [resource_ref(item, f"/source_refs/{index}") for index, item in enumerate(source_refs)]
    if current["candidate_ref"] != expected_candidate:
        _fail("E_CHANGE_DRIFT", "/candidate_ref", "candidate binding changed")
    if current["environment_ref"] != expected_environment:
        _fail("E_CHANGE_DRIFT", "/environment_ref", "environment binding changed")
    if current["source_refs"] != expected_sources:
        _fail("E_CHANGE_DRIFT", "/source_refs", "source binding changed")


__all__ = ["CHANGE_RECORD_TYPE", "build_change_report", "validate_change_report", "assert_change_current"]
