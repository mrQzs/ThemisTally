"""Closed, provenance-bound records shared by the built-in task plugins."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any, Dict, Iterable, Mapping, Tuple


FAMILIES = {"analysis-report", "change-report", "docs-change", "docs-check", "regression-plan", "mutation-review", "check-plan", "review-bundle"}
STATUSES = {"DRAFT_VALIDATED", "READY", "PASS", "FAIL", "UNKNOWN", "BLOCKED", "NOT_RUN", "REFERENCE_ONLY"}
HEX64 = re.compile(r"^[0-9a-f]{64}$")
MAX_BYTES = 1_048_576
MAX_DEPTH = 32


class ArtifactError(ValueError):
    def __init__(self, code: str, path: str, message: str):
        self.code, self.path = code, path
        super().__init__(f"{code} at {path}: {message}")


def _fail(code: str, path: str, message: str) -> None:
    raise ArtifactError(code, path, message)


def canonical_bytes(value: Any) -> bytes:
    try:
        raw = (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ArtifactError("E_ARTIFACT_JSON", "/", str(exc)) from exc
    if len(raw) > MAX_BYTES:
        _fail("E_ARTIFACT_SIZE", "/", "artifact exceeds byte limit")
    return raw


def digest(value: Any) -> str:
    return hashlib.sha256(value if isinstance(value, bytes) else canonical_bytes(value)).hexdigest()


def resource_ref(value: Any, path: str = "/resource_ref") -> Dict[str, str]:
    if not isinstance(value, dict) or set(value) != {"kind", "id", "path", "sha256"}:
        _fail("E_ARTIFACT_REF", path, "closed ResourceRef required")
    if any(not isinstance(value[x], str) or not value[x] for x in ("kind", "id", "path")):
        _fail("E_ARTIFACT_REF", path, "kind/id/path must be non-empty strings")
    if not isinstance(value["sha256"], str) or not HEX64.fullmatch(value["sha256"]):
        _fail("E_ARTIFACT_REF", f"{path}/sha256", "lowercase SHA-256 required")
    normalized = value["path"].replace("\\", "/")
    if normalized.startswith("/") or ".." in normalized.split("/"):
        _fail("E_ARTIFACT_PATH", f"{path}/path", "path must stay within the candidate")
    return {"kind": value["kind"], "id": value["id"], "path": normalized, "sha256": value["sha256"]}


def source_anchor(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"ref", "start_byte", "end_byte", "excerpt_sha256"}:
        _fail("E_ARTIFACT_SOURCE", "/source_anchor", "closed source anchor required")
    result = resource_ref(value["ref"], "/source_anchor/ref")
    if type(value["start_byte"]) is not int or type(value["end_byte"]) is not int or value["start_byte"] < 0 or value["end_byte"] <= value["start_byte"]:
        _fail("E_ARTIFACT_SOURCE", "/source_anchor", "invalid byte range")
    if not isinstance(value["excerpt_sha256"], str) or not HEX64.fullmatch(value["excerpt_sha256"]):
        _fail("E_ARTIFACT_SOURCE", "/source_anchor/excerpt_sha256", "lowercase SHA-256 required")
    return {"ref": result, "start_byte": value["start_byte"], "end_byte": value["end_byte"], "excerpt_sha256": value["excerpt_sha256"]}


def _depth(value: Any, level: int = 0) -> None:
    if level > MAX_DEPTH:
        _fail("E_ARTIFACT_DEPTH", "/", "artifact nesting exceeds limit")
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                _fail("E_ARTIFACT_SCHEMA", "/", "object keys must be text")
            _depth(child, level + 1)
    elif isinstance(value, list):
        for child in value:
            _depth(child, level + 1)


def _producer(value: Any) -> Dict[str, str]:
    if not isinstance(value, dict) or set(value) != {"kind", "id", "version"}:
        _fail("E_ARTIFACT_PRODUCER", "/producer", "closed producer identity required")
    if any(not isinstance(value[x], str) or not value[x] for x in ("kind", "id", "version")):
        _fail("E_ARTIFACT_PRODUCER", "/producer", "producer fields must be non-empty strings")
    return dict(value)


def validate_artifact(record: Mapping[str, Any]) -> Dict[str, Any]:
    required = {"record_type", "schema_version", "artifact_id", "producer", "status", "source_refs", "candidate_ref", "environment_ref", "payload"}
    if not isinstance(record, dict) or set(record) != required:
        _fail("E_ARTIFACT_SCHEMA", "/", "artifact has unknown or missing fields")
    if record["record_type"] not in FAMILIES or record["schema_version"] != 1:
        _fail("E_ARTIFACT_VERSION", "/record_type", "unsupported artifact family/version")
    if not isinstance(record["artifact_id"], str) or not record["artifact_id"]:
        _fail("E_ARTIFACT_SCHEMA", "/artifact_id", "non-empty artifact id required")
    _producer(record["producer"])
    if record["status"] not in STATUSES:
        _fail("E_ARTIFACT_STATUS", "/status", "unknown artifact status")
    refs = record["source_refs"]
    if not isinstance(refs, list) or len({digest(x) for x in refs}) != len(refs):
        _fail("E_ARTIFACT_REF", "/source_refs", "unique source refs required")
    normalized = [resource_ref(x, f"/source_refs/{i}") for i, x in enumerate(refs)]
    candidate = None if record["candidate_ref"] is None else resource_ref(record["candidate_ref"], "/candidate_ref")
    environment = None if record["environment_ref"] is None else resource_ref(record["environment_ref"], "/environment_ref")
    if not isinstance(record["payload"], dict):
        _fail("E_ARTIFACT_SCHEMA", "/payload", "payload must be an object")
    _depth(record)
    result = copy.deepcopy(dict(record)); result["source_refs"] = normalized; result["candidate_ref"] = candidate; result["environment_ref"] = environment
    return result


def validate_catalog(catalog: Mapping[str, Any]) -> Dict[str, Any]:
    if not isinstance(catalog, dict) or set(catalog) != {"record_type", "schema_version", "plugins"}:
        _fail("E_CATALOG_SCHEMA", "/", "closed catalog required")
    if catalog["record_type"] != "builtin-task-plugin-catalog" or catalog["schema_version"] != 1 or not isinstance(catalog["plugins"], list):
        _fail("E_CATALOG_SCHEMA", "/", "invalid catalog header")
    ids = []
    for i, item in enumerate(catalog["plugins"]):
        if not isinstance(item, dict) or set(item) != {"plugin_id", "version", "manifest_ref", "lock_ref"}:
            _fail("E_CATALOG_SCHEMA", f"/plugins/{i}", "catalog item is not closed")
        ids.append(item["plugin_id"]); resource_ref(item["manifest_ref"], f"/plugins/{i}/manifest_ref"); resource_ref(item["lock_ref"], f"/plugins/{i}/lock_ref")
    if len(set(ids)) != len(ids):
        _fail("E_CATALOG_SCHEMA", "/plugins", "duplicate plugin id")
    return copy.deepcopy(dict(catalog))


__all__ = ["ArtifactError", "FAMILIES", "canonical_bytes", "digest", "resource_ref", "source_anchor", "validate_artifact", "validate_catalog"]
