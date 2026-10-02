"""Catalog selection and readiness projection for the 08 plugin directory."""
from __future__ import annotations
from copy import deepcopy
from typing import Any, Mapping, Sequence
from .builtin_artifacts import ArtifactError, validate_catalog


def _err(code: str, message: str) -> None:
    raise ArtifactError(code, "/catalog", message)


def build_catalog(*, plugins: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    rows = []
    for item in plugins:
        if not isinstance(item, Mapping) or set(item) != {"plugin_id", "version", "manifest_ref", "lock_ref"}:
            _err("E_CATALOG", "catalog plugin rows are closed")
        rows.append(dict(item))
    rows.sort(key=lambda row: (row["plugin_id"], row["version"]))
    return validate_catalog({"record_type": "builtin-task-plugin-catalog", "schema_version": 1, "plugins": rows})


def project_catalog_readiness(catalog: Mapping[str, Any], *, requested: Sequence[str],
                              dependencies_ready: bool = True, platform_ready: bool = True) -> dict[str, Any]:
    catalog = validate_catalog(catalog)
    if not isinstance(requested, Sequence) or isinstance(requested, (str, bytes)) or any(type(x) is not str or not x for x in requested):
        _err("E_READINESS", "requested plugin IDs required")
    index = {row["plugin_id"]: row for row in catalog["plugins"]}
    missing = sorted(set(requested) - set(index))
    selected = sorted(set(requested) & set(index))
    reasons = []
    if missing:
        reasons.append("MISSING_PLUGIN")
    if not dependencies_ready:
        reasons.append("DEPENDENCIES_NOT_READY")
    if not platform_ready:
        reasons.append("PLATFORM_BLOCKED")
    status = "READY" if selected and not reasons else ("NOT_RUN" if not reasons and not selected else "BLOCKED")
    return {"status": status, "selected": selected, "missing": missing,
            "reasons": reasons, "dispatch_eligibility": "not_evaluated"}

__all__ = ["build_catalog", "project_catalog_readiness"]
