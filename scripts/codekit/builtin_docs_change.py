"""Offline docs-change producer for the builtin task plugins.

This module only creates a deterministic, provenance-bound business artifact. It
never writes a repository, invokes a command, or contacts a network service.
"""
from __future__ import annotations

import copy
import hashlib
import re
from typing import Any, Mapping, Optional, Sequence

from .builtin_artifacts import ArtifactError, digest, resource_ref, source_anchor, validate_artifact

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _path(value: Any, field: str = "/path") -> str:
    if not isinstance(value, str) or not value or len(value) > 512:
        raise ArtifactError("E_DOCS_PATH", field, "non-empty relative path required")
    normalized = value.replace("\\", "/")
    if normalized.startswith("/") or ":" in normalized or any(p in {"", ".", ".."} for p in normalized.split("/")):
        raise ArtifactError("E_DOCS_PATH", field, "absolute, empty and traversal paths are forbidden")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in normalized):
        raise ArtifactError("E_DOCS_PATH", field, "control character in path")
    return normalized


def _sha(value: Any, field: str) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, bytes):
        return hashlib.sha256(value).hexdigest()
    if isinstance(value, str) and _HEX64.fullmatch(value):
        return value
    raise ArtifactError("E_DOCS_HASH", field, "sha256 hex or null required")


def _anchors(value: Any) -> list:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ArtifactError("E_DOCS_SOURCE", "/source_anchors", "array required")
    return [source_anchor(item) for item in value]


def build_docs_change(
    before: Mapping[str, bytes],
    after: Mapping[str, bytes],
    *,
    writable_paths: Sequence[str],
    protected_paths: Sequence[str] = (),
    source_refs: Sequence[Mapping[str, str]] = (),
    candidate_ref: Optional[Mapping[str, str]] = None,
    environment_ref: Optional[Mapping[str, str]] = None,
    artifact_id: str = "docs-change",
    producer_id: str = "docs-change",
    producer_version: str = "1.0.0",
    status: str = "DRAFT_VALIDATED",
    purpose: str = "documentation maintenance",
    reader: str = "repository users",
) -> dict:
    """Build a deterministic docs-change artifact from fixed byte mappings.

    ``before`` and ``after`` are already-frozen in-memory snapshots. Every
    changed path must be explicitly writable and end in ``.md`` or ``.markdown``;
    protected paths always win over writable paths.
    """
    if not isinstance(before, Mapping) or not isinstance(after, Mapping):
        raise ArtifactError("E_DOCS_SNAPSHOT", "/", "before and after mappings required")
    if any(type(value) is not bytes for value in before.values()) or any(type(value) is not bytes for value in after.values()):
        raise ArtifactError("E_DOCS_SNAPSHOT", "/", "snapshot values must be bytes")
    if not isinstance(writable_paths, Sequence) or isinstance(writable_paths, (str, bytes)):
        raise ArtifactError("E_DOCS_SCOPE", "/writable_paths", "writable paths sequence required")
    if not isinstance(protected_paths, Sequence) or isinstance(protected_paths, (str, bytes)):
        raise ArtifactError("E_DOCS_SCOPE", "/protected_paths", "protected paths sequence required")
    if not isinstance(source_refs, Sequence) or isinstance(source_refs, (str, bytes)):
        raise ArtifactError("E_DOCS_SOURCE", "/source_refs", "source refs sequence required")
    writable = {_path(p, "/writable_paths") for p in writable_paths}
    protected = {_path(p, "/protected_paths") for p in protected_paths}
    if not writable.isdisjoint(protected):
        raise ArtifactError("E_DOCS_PROTECTED", "/writable_paths", "protected path cannot be writable")
    all_paths = {_path(p) for p in before.keys()} | {_path(p) for p in after.keys()}
    changes = []
    for path in sorted(all_paths):
        old = before.get(path)
        new = after.get(path)
        if old == new:
            continue
        if path not in writable:
            raise ArtifactError("E_DOCS_SCOPE", path, "changed path is outside writable scope")
        if path in protected:
            raise ArtifactError("E_DOCS_PROTECTED", path, "protected path cannot change")
        if not (path.endswith(".md") or path.endswith(".markdown")):
            raise ArtifactError("E_DOCS_SCOPE", path, "docs-change accepts Markdown paths only")
        kind = "add" if old is None else "delete" if new is None else "modify"
        changes.append({
            "path": path,
            "kind": kind,
            "before_sha256": None if old is None else hashlib.sha256(bytes(old)).hexdigest(),
            "after_sha256": None if new is None else hashlib.sha256(bytes(new)).hexdigest(),
            "purpose": purpose,
            "reader": reader,
            "source_anchors": [],
        })
    for ref in source_refs:
        resource_ref(ref)
    if type(status) is not str:
        raise ArtifactError("E_DOCS_SCHEMA", "/status", "status must be text")
    if status == "PASS":
        raise ArtifactError("E_DOCS_PRODUCTION_GATE", "/status", "PASS requires a trusted dispatcher receipt")
    payload = {"changes": changes, "scope": {"writable": sorted(writable), "protected": sorted(protected)}, "mapping_version": 1}
    record = {
        "record_type": "docs-change", "schema_version": 1, "artifact_id": artifact_id,
        "producer": {"kind": "builtin-plugin", "id": producer_id, "version": producer_version},
        "status": status, "source_refs": [dict(x) for x in source_refs],
        "candidate_ref": None if candidate_ref is None else dict(candidate_ref),
        "environment_ref": None if environment_ref is None else dict(environment_ref), "payload": payload,
    }
    return validate_artifact(record)


def validate_docs_change(record: Mapping[str, Any]) -> dict:
    """Validate a docs-change envelope and its closed payload fields."""
    value = validate_artifact(record)
    if value["record_type"] != "docs-change":
        raise ArtifactError("E_DOCS_TYPE", "/record_type", "docs-change record required")
    payload = value["payload"]
    if set(payload) != {"changes", "scope", "mapping_version"} or payload["mapping_version"] != 1:
        raise ArtifactError("E_DOCS_SCHEMA", "/payload", "closed docs-change payload required")
    if not isinstance(payload["changes"], list) or not isinstance(payload["scope"], dict) or set(payload["scope"]) != {"writable", "protected"}:
        raise ArtifactError("E_DOCS_SCHEMA", "/payload", "invalid changes or scope")
    for i, item in enumerate(payload["changes"]):
        required = {"path", "kind", "before_sha256", "after_sha256", "purpose", "reader", "source_anchors"}
        if not isinstance(item, dict) or set(item) != required:
            raise ArtifactError("E_DOCS_SCHEMA", "/payload/changes/%d" % i, "closed change row required")
        path = _path(item["path"], "/payload/changes/%d/path" % i)
        if item["kind"] not in {"add", "modify", "delete"}:
            raise ArtifactError("E_DOCS_SCHEMA", path, "unsupported change kind")
        _sha(item["before_sha256"], "/payload/changes/%d/before_sha256" % i)
        _sha(item["after_sha256"], "/payload/changes/%d/after_sha256" % i)
        if item["kind"] == "add" and item["before_sha256"] is not None:
            raise ArtifactError("E_DOCS_SCHEMA", path, "add must not have before hash")
        if item["kind"] == "delete" and item["after_sha256"] is not None:
            raise ArtifactError("E_DOCS_SCHEMA", path, "delete must not have after hash")
        if not isinstance(item["purpose"], str) or not item["purpose"] or not isinstance(item["reader"], str) or not item["reader"]:
            raise ArtifactError("E_DOCS_SCHEMA", path, "purpose and reader are required")
        anchors = _anchors(item["source_anchors"])
        declared = {(ref["kind"], ref["id"], ref["path"], ref["sha256"]) for ref in value["source_refs"]}
        for anchor_index, anchor in enumerate(anchors):
            ref = anchor["ref"]
            if (ref["kind"], ref["id"], ref["path"], ref["sha256"]) not in declared:
                raise ArtifactError("E_DOCS_PROVENANCE", "/payload/changes/%d/source_anchors/%d/ref" % (i, anchor_index), "anchor reference is not declared in source_refs")
    return copy.deepcopy(value)


__all__ = ["build_docs_change", "validate_docs_change"]

