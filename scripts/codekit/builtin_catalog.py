"""Catalog selection and readiness projection for the 08 plugin directory."""
from __future__ import annotations
import re
from pathlib import Path
from os import PathLike
from typing import Any, Mapping, Sequence
from .builtin_artifacts import ArtifactError, canonical_bytes, validate_catalog
from .plugins import VERSION_RE, validate_lock, validate_manifest
from .protocols import ProtocolError, strict_json_loads

REQUIRED_PLUGIN_IDS = frozenset({"repo-analysis", "code-change", "python-checks", "docs-change", "docs-checks", "regression-tests", "mutation-review"})
REQUIRED_RECIPE_IDS = frozenset({"repair", "docs", "regression"})


def _err(code: str, message: str) -> None:
    raise ArtifactError(code, "/catalog", message)


def _root(value: str | PathLike[str] | Path, *, kind: str) -> Path:
    if not isinstance(value, (str, PathLike, Path)) or isinstance(value, (bytes, bytearray)):
        _err(kind, "fixture root path required")
    try:
        return Path(value)
    except (TypeError, ValueError) as exc:
        _err(kind, "fixture root path required")
        raise AssertionError from exc


def _read_json(path: Path, *, kind: str) -> Any:
    try:
        return strict_json_loads(path.read_bytes())
    except (OSError, UnicodeError, ProtocolError) as exc:
        _err(kind, f"invalid JSON fixture {path.name}")
        raise AssertionError from exc


def _safe_file(path: Path, root: Path, *, kind: str) -> Path:
    """Resolve a fixture file without allowing symlink/junction escapes."""
    try:
        root_resolved = root.resolve(strict=True)
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        _err(kind, f"fixture path cannot be resolved: {path.name}")
        raise AssertionError from exc
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        _err(kind, f"fixture path escapes root: {path.name}")
        raise AssertionError from exc
    current = root_resolved
    try:
        relative = path.relative_to(root)
    except ValueError:
        relative = Path(path.name)
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            _err(kind, f"symlink fixture path is not allowed: {path.name}")
    if not resolved.is_file():
        _err(kind, f"fixture file is missing: {path.name}")
    return resolved


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
    result = validate_catalog({"record_type": "builtin-task-plugin-catalog", "schema_version": 1, "plugins": rows})
    try:
        canonical_bytes(result)
    except ArtifactError as exc:
        _err(exc.code, "catalog exceeds canonical JSON limits")
    return result


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
    base = _root(root, kind="E_CATALOG_FIXTURE")
    try:
        base = base.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        _err("E_CATALOG_FIXTURE", "fixture root cannot be resolved")
        raise AssertionError from exc
    rows = []
    for plugin_id in sorted(REQUIRED_PLUGIN_IDS):
        manifest_path = _safe_file(base / plugin_id / "manifest.json", base, kind="E_CATALOG_FIXTURE")
        lock_path = _safe_file(base / plugin_id / "lock.json", base, kind="E_CATALOG_FIXTURE")
        manifest = validate_manifest(_read_json(manifest_path, kind="E_CATALOG_FIXTURE"))
        lock = validate_lock(_read_json(lock_path, kind="E_CATALOG_FIXTURE"), {plugin_id: manifest})
        if manifest["plugin_id"] != plugin_id or len(lock["plugins"]) != 1 or lock["plugins"][0]["plugin_id"] != plugin_id:
            _err("E_CATALOG_IDENTITY", f"manifest/lock identity mismatch for {plugin_id}")
        # Resource refs are repository-relative.  Verify their bytes while
        # loading the catalog so a checked-in manifest cannot claim content it
        # does not actually bind.
        # ResourceRef paths are candidate-relative even when callers provide
        # an absolute fixture root (as isolated tests commonly do).  Resolve
        # the manifest's declared resource paths from that same fixture root,
        # then emit the manifest/lock references relative to its parent.
        project_root = base.parent.resolve(strict=True)
        manifest_ref_path = manifest_path.relative_to(project_root).as_posix()
        lock_ref_path = lock_path.relative_to(project_root).as_posix()
        for resource in manifest.get("resources", []):
            resource_path = _safe_file(project_root / resource["path"], project_root, kind="E_CATALOG_RESOURCE")
            if _sha_file(resource_path) != resource["sha256"]:
                _err("E_CATALOG_RESOURCE", f"resource bytes do not match {resource['path']}")
        rows.append({"plugin_id": plugin_id, "version": manifest["version"],
                     "manifest_ref": {"kind": "file", "id": f"{plugin_id}.manifest", "path": manifest_ref_path, "sha256": _sha_file(manifest_path)},
                     "lock_ref": {"kind": "file", "id": f"{plugin_id}.lock", "path": lock_ref_path, "sha256": _sha_file(lock_path)}})
    return build_catalog(plugins=rows)


def load_builtin_recipes(root: str | Path = "workflows") -> dict[str, Any]:
    base = _root(root, kind="E_RECIPE_FIXTURE")
    try:
        base = base.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        _err("E_RECIPE_FIXTURE", "fixture root cannot be resolved")
        raise AssertionError from exc
    recipes = []
    for recipe_id in sorted(REQUIRED_RECIPE_IDS):
        path = _safe_file(base / f"{recipe_id}.json", base, kind="E_RECIPE_FIXTURE")
        value = _read_json(path, kind="E_RECIPE_FIXTURE")
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
                  or not VERSION_RE.fullmatch(stage["plugin_version"])):
                _err("E_RECIPE_FIXTURE", "plugin stages require a registered plugin and exact version")
            visited.add(stage["id"])
        recipes.append(value)
    return {"record_type": "builtin-task-workflow-recipes", "schema_version": 1, "recipes": recipes}


def _sha_file(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()

__all__ = ["REQUIRED_PLUGIN_IDS", "REQUIRED_RECIPE_IDS", "build_catalog", "load_builtin_catalog", "load_builtin_recipes", "project_catalog_readiness"]
