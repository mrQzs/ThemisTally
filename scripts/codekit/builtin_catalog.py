"""Catalog selection and readiness projection for the 08 plugin directory."""
from __future__ import annotations
from copy import deepcopy
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence
from .builtin_artifacts import ArtifactError, validate_catalog
from .plugins import validate_lock, validate_manifest

REQUIRED_PLUGIN_IDS = frozenset({"repo-analysis", "code-change", "python-checks", "docs-change", "docs-checks", "regression-tests", "mutation-review"})
REQUIRED_RECIPE_IDS = frozenset({"repair", "docs", "regression"})


def _err(code: str, message: str) -> None:
    raise ArtifactError(code, "/catalog", message)


def build_catalog(*, plugins: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not isinstance(plugins, Sequence) or isinstance(plugins, (str, bytes)):
        _err("E_CATALOG", "plugin rows sequence required")
    rows = []
    for item in plugins:
        if not isinstance(item, Mapping) or set(item) != {"plugin_id", "version", "manifest_ref", "lock_ref"}:
            _err("E_CATALOG", "catalog plugin rows are closed")
        rows.append(dict(item))
    validate_catalog({"record_type": "builtin-task-plugin-catalog", "schema_version": 1, "plugins": rows})
    rows.sort(key=lambda row: (row["plugin_id"], row["version"]))
    return validate_catalog({"record_type": "builtin-task-plugin-catalog", "schema_version": 1, "plugins": rows})


def project_catalog_readiness(catalog: Mapping[str, Any], *, requested: Sequence[str],
                              dependencies_ready: bool = True, platform_ready: bool = True) -> dict[str, Any]:
    catalog = validate_catalog(catalog)
    if type(dependencies_ready) is not bool or type(platform_ready) is not bool:
        _err("E_READINESS", "readiness flags must be boolean")
    if not isinstance(requested, Sequence) or isinstance(requested, (str, bytes)) or any(type(x) is not str or not x for x in requested):
        _err("E_READINESS", "requested plugin IDs required")
    if len(set(requested)) != len(requested):
        _err("E_READINESS", "requested plugin IDs must be unique")
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


def load_builtin_catalog(root: str | Path = "plugins") -> dict[str, Any]:
    """Load and validate the seven checked-in offline plugin fixtures."""
    base = Path(root)
    rows = []
    for plugin_id in sorted(REQUIRED_PLUGIN_IDS):
        manifest_path = base / plugin_id / "manifest.json"
        lock_path = base / plugin_id / "lock.json"
        if not manifest_path.is_file() or not lock_path.is_file():
            _err("E_CATALOG_FIXTURE", f"missing manifest/lock for {plugin_id}")
        manifest = validate_manifest(json.loads(manifest_path.read_text(encoding="utf-8")))
        lock = validate_lock(json.loads(lock_path.read_text(encoding="utf-8")), {plugin_id: manifest})
        if manifest["plugin_id"] != plugin_id or len(lock["plugins"]) != 1 or lock["plugins"][0]["plugin_id"] != plugin_id:
            _err("E_CATALOG_IDENTITY", f"manifest/lock identity mismatch for {plugin_id}")
        # Resource refs are repository-relative.  Verify their bytes while
        # loading the catalog so a checked-in manifest cannot claim content it
        # does not actually bind.
        project_root = base.parent if base.name == "plugins" else Path(".")
        for resource in manifest.get("resources", []):
            resource_path = project_root / resource["path"]
            if not resource_path.is_file() or _sha_file(resource_path) != resource["sha256"]:
                _err("E_CATALOG_RESOURCE", f"resource bytes do not match {resource['path']}")
        rows.append({"plugin_id": plugin_id, "version": manifest["version"],
                     "manifest_ref": {"kind": "file", "id": f"{plugin_id}.manifest", "path": str(manifest_path).replace("\\", "/"), "sha256": _sha_file(manifest_path)},
                     "lock_ref": {"kind": "file", "id": f"{plugin_id}.lock", "path": str(lock_path).replace("\\", "/"), "sha256": _sha_file(lock_path)}})
    return build_catalog(plugins=rows)


def load_builtin_recipes(root: str | Path = "workflows") -> dict[str, Any]:
    base = Path(root)
    recipes = []
    for recipe_id in sorted(REQUIRED_RECIPE_IDS):
        path = base / f"{recipe_id}.json"
        if not path.is_file():
            _err("E_RECIPE_FIXTURE", f"missing recipe {recipe_id}")
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or set(value) != {"record_type", "schema_version", "recipe_id", "recipe_version", "stages", "evidence_status"} or value["record_type"] != "builtin-workflow-recipe" or value["schema_version"] != 1 or value["recipe_id"] != recipe_id or value["evidence_status"] != "REFERENCE_ONLY":
            _err("E_RECIPE_FIXTURE", f"invalid recipe {recipe_id}")
        if (not isinstance(value["stages"], list) or any(not isinstance(stage, Mapping) for stage in value["stages"])
                or any(set(stage) != {"id", "kind", "depends_on", "execution", "plugin_id", "plugin_version"} for stage in value["stages"])
                or [stage.get("kind") for stage in value["stages"]] != ["analysis", "change", "freeze", "check", "review"]):
            _err("E_RECIPE_FIXTURE", f"recipe {recipe_id} must have five ordered business stages")
        if type(value["schema_version"]) is not int or type(value["recipe_version"]) is not int or value["recipe_version"] < 1:
            _err("E_RECIPE_FIXTURE", f"invalid recipe version for {recipe_id}")
        visited = set()
        for stage in value["stages"]:
            if type(stage["id"]) is not str or not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", stage["id"]) or stage["id"] in visited:
                _err("E_RECIPE_FIXTURE", "stage IDs must be unique lowercase names")
            deps = stage["depends_on"]
            if not isinstance(deps, list) or any(type(dep) is not str or dep not in visited for dep in deps) or len(set(deps)) != len(deps):
                _err("E_RECIPE_FIXTURE", "stage dependencies must precede their stage")
            if stage["kind"] in {"freeze", "review"}:
                if stage["execution"] != "core" or stage["plugin_id"] is not None or stage["plugin_version"] is not None:
                    _err("E_RECIPE_FIXTURE", "freeze/review belong to core")
            elif (stage["execution"] != "plugin" or stage["plugin_id"] not in REQUIRED_PLUGIN_IDS
                  or type(stage["plugin_version"]) is not str
                  or not re.fullmatch(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", stage["plugin_version"])):
                _err("E_RECIPE_FIXTURE", "plugin stages require a registered plugin and exact version")
            visited.add(stage["id"])
        recipes.append(value)
    return {"record_type": "builtin-task-workflow-recipes", "schema_version": 1, "recipes": recipes}


def _sha_file(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()

__all__ = ["REQUIRED_PLUGIN_IDS", "REQUIRED_RECIPE_IDS", "build_catalog", "load_builtin_catalog", "load_builtin_recipes", "project_catalog_readiness"]
