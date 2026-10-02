"""Static shape validation for the 07-T2B baseline-binding record.

This module deliberately validates declarations and evidence references only.
It does not execute Git, resolve a repository, prove object existence or
ancestor relationships, check content coverage, or grant authorization.
Those facts belong to a later, explicitly read-only Git probe and trusted
authorization layer.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from . import protocols

BASELINE_RECORD_TYPE = "baseline-binding"
BASELINE_SCHEMA_VERSION = 1
COVERAGE_MODES = frozenset(("exact_tree", "pinned_artifact_set", "revalidated_integration"))
MAX_EVIDENCE_REFS = 1024


@dataclass(frozen=True)
class BaselineBinding:
    """Immutable validated view of a structural baseline binding.

    The view records claims that a later trusted layer must verify.  It is not
    evidence that the referenced Git objects exist or that the declared
    authorization and coverage are true.
    """

    record: Mapping[str, Any]

    @property
    def repo_id(self) -> str:
        return self.record["repo_id"]

    @property
    def environment_id(self) -> str:
        return self.record["environment_id"]

    @property
    def object_format(self) -> str:
        return self.record["object_format"]

    @property
    def base_sha(self) -> str:
        return self.record["base_sha"]

    @property
    def tree_sha(self) -> str:
        return self.record["tree_sha"]

    @property
    def coverage_mode(self) -> str:
        return self.record["coverage_mode"]


def validate_baseline_binding(document: Any) -> BaselineBinding:
    """Validate the T2B-S structural profile and return a detached immutable view.

    The input must already be strict JSON when it originated as bytes.  Git
    object existence, tree contents, acceptance, authorization, currentness,
    and multi-upstream integration remain intentionally unverified.
    """
    protocols.check_json_value(document, max_bytes=protocols.DEFAULT_MAX_BYTES)
    root = _expect_dict(document, "", "baseline_binding")
    _closed(root, {
        "record_type", "schema_version", "repo_id", "environment_id", "object_format",
        "base_sha", "tree_sha", "upstream_results", "coverage_mode", "coverage_refs",
        "authorization_ref", "observation_ref", "guard_version",
    }, "")
    _expect_const(root, "record_type", BASELINE_RECORD_TYPE)
    protocols.require_schema_version(root, {BASELINE_SCHEMA_VERSION})
    protocols.validate_logical_id(root.get("repo_id"), field="/repo_id")
    protocols.validate_logical_id(root.get("environment_id"), field="/environment_id")

    object_format = root.get("object_format")
    if type(object_format) is not str or object_format not in ("sha1", "sha256"):
        _error("E_GIT_FORMAT_UNSUPPORTED", "/object_format", "object_format_unsupported")
    protocols.validate_git_oid(root.get("base_sha"), object_format, field="/base_sha")
    protocols.validate_git_oid(root.get("tree_sha"), object_format, field="/tree_sha")

    upstream_results = _expect_list(root.get("upstream_results"), "/upstream_results", max_items=MAX_EVIDENCE_REFS)
    for index, ref in enumerate(upstream_results):
        _validate_ref(ref, f"/upstream_results/{index}")

    coverage_mode = root.get("coverage_mode")
    if type(coverage_mode) is not str or coverage_mode not in COVERAGE_MODES:
        _error("E_SCHEMA_FIELDS", "/coverage_mode", "coverage_mode_unsupported")
    coverage_refs = _expect_list(root.get("coverage_refs"), "/coverage_refs", max_items=MAX_EVIDENCE_REFS,
                                 nonempty=True)
    for index, ref in enumerate(coverage_refs):
        _validate_ref(ref, f"/coverage_refs/{index}")
    _validate_ref(root.get("authorization_ref"), "/authorization_ref")
    _validate_ref(root.get("observation_ref"), "/observation_ref")
    protocols.require_int(root.get("guard_version"), field="/guard_version", minimum=1)

    frozen = _freeze(copy.deepcopy(root))
    return BaselineBinding(frozen)


def parse_baseline_binding(raw: bytes, *, max_bytes: int = protocols.DEFAULT_MAX_BYTES) -> BaselineBinding:
    """Strictly decode and validate one baseline-binding JSON document."""
    return validate_baseline_binding(protocols.strict_json_loads(raw, max_bytes=max_bytes))


def _validate_ref(ref: Any, field: str) -> None:
    obj = _expect_dict(ref, field, "resource_ref")
    _closed(obj, {"kind", "id", "sha256", "path"}, field,
            required={"kind", "id", "sha256", "path"})
    protocols.validate_resource_kind(obj.get("kind"), field=f"{field}/kind")
    ref_id = protocols.validate_logical_id(obj.get("id"), field=f"{field}/id")
    if ref_id.lower() in {"latest", "head", "current"}:
        _error("E_SCHEMA_FIELDS", f"{field}/id", "mutable_alias_forbidden")
    protocols.validate_sha256(obj.get("sha256"), field=f"{field}/sha256")
    protocols.validate_business_path(obj.get("path"), field=f"{field}/path")


def _expect_dict(value: Any, field: str, reason: str) -> dict[str, Any]:
    if type(value) is not dict:
        _error("E_SCHEMA_TYPE", field, f"{reason}_object_required")
    return value


def _expect_list(value: Any, field: str, *, max_items: int, nonempty: bool = False) -> list[Any]:
    if type(value) is not list:
        _error("E_SCHEMA_TYPE", field, "array_required")
    if len(value) > max_items:
        _error("E_JSON_LIMIT", field, "array_limit_exceeded")
    if nonempty and not value:
        _error("E_SCHEMA_FIELDS", field, "nonempty_array_required")
    return value


def _closed(value: dict[str, Any], allowed: set[str], field: str,
            *, required: set[str] | None = None) -> None:
    if required is None:
        required = allowed
    unknown = set(value) - allowed
    missing = required - set(value)
    if unknown or missing:
        _error("E_SCHEMA_FIELDS", field, "closed_object_fields")


def _expect_const(value: dict[str, Any], key: str, expected: Any) -> None:
    if value.get(key) != expected:
        _error("E_SCHEMA_FIELDS", f"/{key}", "constant_mismatch")


def _error(code: str, field: str, reason: str) -> None:
    raise protocols.ProtocolError(code, field=field or None, phase="baseline", reason=reason)


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


__all__ = [
    "BASELINE_RECORD_TYPE", "BASELINE_SCHEMA_VERSION", "COVERAGE_MODES",
    "BaselineBinding", "parse_baseline_binding", "validate_baseline_binding",
]
