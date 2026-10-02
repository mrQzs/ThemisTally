"""Strict offline plugin manifest and content-lock validation."""

from __future__ import annotations

import copy
import hashlib
import json
import posixpath
import ntpath
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Sequence, Tuple


VERSION_RE = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
PLUGIN_ID = re.compile(r"^[a-z][a-z0-9-]{0,63}$")


class PluginError(ValueError):
    def __init__(self, code: str, path: str, message: str):
        self.code, self.path = code, path
        super().__init__(f"{code} at {path}: {message}")


def _fail(code: str, path: str, message: str) -> None:
    raise PluginError(code, path, message)


def canonical_bytes(value: Any) -> bytes:
    try:
        return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise PluginError("E_PLUGIN_JSON", "/", str(exc)) from exc


def digest(value: Any) -> str:
    return hashlib.sha256(value if isinstance(value, bytes) else canonical_bytes(value)).hexdigest()


def _identifier(value: Any, path: str) -> None:
    if not isinstance(value, str) or not PLUGIN_ID.fullmatch(value):
        _fail("E_PLUGIN_IDENTITY", path, "lowercase plugin id required")


def _strings(value: Any, path: str) -> None:
    if not isinstance(value, list) or any(not isinstance(x, str) or not x or "\0" in x for x in value):
        _fail("E_PLUGIN_SCHEMA", path, "unique non-empty string array required")
    if len(set(value)) != len(value):
        _fail("E_PLUGIN_SCHEMA", path, "duplicate value")


def resource_ref(value: Any, path: str) -> Dict[str, str]:
    if not isinstance(value, dict) or set(value) != {"kind", "id", "path", "sha256"}:
        _fail("E_PLUGIN_RESOURCE", path, "closed ResourceRef required")
    for key in ("kind", "id", "path"):
        if not isinstance(value[key], str) or not value[key]:
            _fail("E_PLUGIN_RESOURCE", f"{path}/{key}", "non-empty string required")
    name = value["path"].replace("\\", "/")
    if name.startswith("/") or ntpath.splitdrive(name)[0] or name.startswith("./") or any(part in {"", ".", ".."} for part in name.split("/")) or any(ord(ch) < 32 for ch in name):
        _fail("E_PLUGIN_PATH", f"{path}/path", "absolute and traversal paths are forbidden")
    if not isinstance(value["sha256"], str) or not HEX64.fullmatch(value["sha256"]):
        _fail("E_PLUGIN_RESOURCE", f"{path}/sha256", "lowercase SHA-256 required")
    return {"kind": value["kind"], "id": value["id"], "path": name, "sha256": value["sha256"]}


def validate_manifest(manifest: Mapping[str, Any]) -> Dict[str, Any]:
    allowed = {"record_type", "schema_version", "plugin_id", "version", "api_version", "roles", "capabilities",
               "entrypoints", "resources", "depends_on", "conflicts", "checks", "platforms", "permissions"}
    if not isinstance(manifest, dict):
        _fail("E_PLUGIN_SCHEMA", "/", "manifest must be an object")
    if set(manifest) - allowed:
        _fail("E_PLUGIN_UNKNOWN_FIELD", "/", f"unknown fields: {sorted(set(manifest) - allowed)}")
    required = {"record_type", "schema_version", "plugin_id", "version", "api_version", "roles", "capabilities", "resources", "checks"}
    if required - set(manifest):
        _fail("E_PLUGIN_SCHEMA", "/", f"missing fields: {sorted(required - set(manifest))}")
    for field in ("record_type", "plugin_id", "version", "api_version"):
        if not isinstance(manifest.get(field), str) or not manifest[field]:
            _fail("E_PLUGIN_SCHEMA", f"/{field}", "non-empty string required")
    if manifest["record_type"] != "builtin-task-plugin-manifest" or type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1:
        _fail("E_PLUGIN_VERSION", "/record_type", "manifest schema version 1 required")
    _identifier(manifest["plugin_id"], "/plugin_id")
    if not VERSION_RE.fullmatch(manifest["version"]):
        _fail("E_PLUGIN_VERSION", "/version", "exact semantic version required")
    if "latest" in manifest["version"].lower() or "latest" in manifest["api_version"].lower():
        _fail("E_PLUGIN_VERSION", "/version", "mutable aliases are forbidden")
    for field in ("roles", "capabilities", "depends_on", "conflicts", "platforms", "permissions"):
        if field in manifest:
            _strings(manifest[field], f"/{field}")
    for field in ("depends_on", "conflicts"):
        for index, name in enumerate(manifest.get(field, [])):
            _identifier(name, f"/{field}/{index}")
    resources = manifest.get("resources", [])
    if not isinstance(resources, list):
        _fail("E_PLUGIN_SCHEMA", "/resources", "resource array required")
    refs = [resource_ref(value, f"/resources/{i}") for i, value in enumerate(resources)]
    if len({(x["kind"], x["id"]) for x in refs}) != len(refs):
        _fail("E_PLUGIN_RESOURCE", "/resources", "duplicate resource identity")
    entrypoints = manifest.get("entrypoints", [])
    _strings(entrypoints, "/entrypoints")
    checks = manifest.get("checks", [])
    if not isinstance(checks, list) or any(not isinstance(x, dict) for x in checks):
        _fail("E_PLUGIN_SCHEMA", "/checks", "check descriptor array required")
    for i, check in enumerate(checks):
        if set(check) != {"id", "command", "deterministic"} or not isinstance(check.get("id"), str) or not check["id"] or "\0" in check["id"] or not isinstance(check.get("command"), list) or not check["command"] or any(not isinstance(arg, str) or not arg or "\0" in arg for arg in check["command"]) or type(check.get("deterministic")) is not bool:
            _fail("E_PLUGIN_CHECK", f"/checks/{i}", "closed id/command/deterministic check required")
        flat = " ".join(str(x) for x in check["command"])
        if any(token in flat.lower() for token in ("importlib", "__import__", "eval(", "exec(", "http://", "https://", "latest")):
            _fail("E_PLUGIN_CHECK", f"/checks/{i}/command", "dynamic import, network and mutable alias are forbidden")
    if len({check["id"] for check in checks}) != len(checks):
        _fail("E_PLUGIN_CHECK", "/checks", "duplicate check id")
    if not manifest["roles"] and (not checks or any(not check["deterministic"] for check in checks)):
        _fail("E_PLUGIN_CHECK", "/checks", "role-free plugins require explicit deterministic checks")
    canonical_bytes(manifest)
    return copy.deepcopy(dict(manifest))


def resolve_plugins(manifests: Mapping[str, Mapping[str, Any]], enabled: Sequence[str]) -> Tuple[Dict[str, Any], ...]:
    if not isinstance(manifests, Mapping):
        _fail("E_PLUGIN_SCHEMA", "/plugins", "manifest registry required")
    _strings(list(enabled) if isinstance(enabled, (tuple, list)) else enabled, "/enabled")
    normalized = {name: validate_manifest(value) for name, value in manifests.items()}
    for name, value in normalized.items():
        if value["plugin_id"] != name:
            _fail("E_PLUGIN_IDENTITY", f"/plugins/{name}/plugin_id", "registry key must match plugin_id")
    for name in enabled:
        if name not in normalized:
            _fail("E_PLUGIN_DEPENDENCY", f"/enabled/{name}", "plugin is not registered")
    result = []
    visiting, visited = set(), set()

    def visit(name: str) -> None:
        if name in visiting:
            _fail("E_PLUGIN_CYCLE", "/depends_on", f"dependency cycle includes {name}")
        if name in visited:
            return
        visiting.add(name)
        manifest = normalized[name]
        for dependency in sorted(manifest.get("depends_on", [])):
            if dependency not in normalized:
                _fail("E_PLUGIN_DEPENDENCY", f"/plugins/{name}/depends_on", f"missing dependency {dependency}")
            visit(dependency)
        visiting.remove(name); visited.add(name); result.append(manifest)

    for name in sorted(enabled):
        visit(name)
    names = {x["plugin_id"] for x in result}
    for manifest in result:
        conflict = names.intersection(manifest.get("conflicts", []))
        if conflict:
            _fail("E_PLUGIN_CONFLICT", f"/plugins/{manifest['plugin_id']}/conflicts", f"enabled conflict {sorted(conflict)}")
    return tuple(result)


def build_lock(manifests: Sequence[Mapping[str, Any]], *, compiler_sha256: str, generation: int = 1) -> Dict[str, Any]:
    if not isinstance(compiler_sha256, str) or not HEX64.fullmatch(compiler_sha256) or type(generation) is not int or generation < 1:
        _fail("E_PLUGIN_LOCK", "/", "compiler hash and positive generation required")
    normalized_manifests = [validate_manifest(x) for x in manifests]
    resolve_plugins({item["plugin_id"]: item for item in normalized_manifests}, [item["plugin_id"] for item in normalized_manifests])
    rows = []
    for manifest in sorted(normalized_manifests, key=lambda x: x["plugin_id"]):
        rows.append({"plugin_id": manifest["plugin_id"], "version": manifest["version"], "manifest_sha256": digest(manifest),
                     "resources": sorted(manifest.get("resources", []), key=lambda x: (x["kind"], x["id"]))})
    lock = {"record_type": "plugin-lock", "schema_version": 1, "generation": generation,
            "compiler_sha256": compiler_sha256, "plugins": rows}
    lock["lock_sha256"] = digest(lock)
    return validate_lock(lock, {manifest["plugin_id"]: manifest for manifest in normalized_manifests})


def validate_lock(lock: Mapping[str, Any], manifests: Mapping[str, Mapping[str, Any]] | None = None) -> Dict[str, Any]:
    required = {"record_type", "schema_version", "generation", "compiler_sha256", "plugins", "lock_sha256"}
    if not isinstance(lock, dict) or set(lock) != required:
        _fail("E_PLUGIN_LOCK", "/", "closed plugin lock required")
    if lock["record_type"] != "plugin-lock" or type(lock["schema_version"]) is not int or lock["schema_version"] != 1 or type(lock["generation"]) is not int or lock["generation"] < 1:
        _fail("E_PLUGIN_LOCK", "/", "invalid lock header")
    for field in ("compiler_sha256", "lock_sha256"):
        if not isinstance(lock[field], str) or not HEX64.fullmatch(lock[field]):
            _fail("E_PLUGIN_LOCK", f"/{field}", "lowercase SHA-256 required")
    if not isinstance(lock["plugins"], list):
        _fail("E_PLUGIN_LOCK", "/plugins", "plugin array required")
    seen = set()
    for index, row in enumerate(lock["plugins"]):
        path = f"/plugins/{index}"
        if not isinstance(row, dict) or set(row) != {"plugin_id", "version", "manifest_sha256", "resources"}:
            _fail("E_PLUGIN_LOCK", path, "closed plugin lock row required")
        _identifier(row["plugin_id"], f"{path}/plugin_id")
        if row["plugin_id"] in seen:
            _fail("E_PLUGIN_LOCK", path, "duplicate plugin id")
        seen.add(row["plugin_id"])
        if not isinstance(row["version"], str) or not VERSION_RE.fullmatch(row["version"]):
            _fail("E_PLUGIN_LOCK", f"{path}/version", "exact semantic version required")
        if not isinstance(row["manifest_sha256"], str) or not HEX64.fullmatch(row["manifest_sha256"]):
            _fail("E_PLUGIN_LOCK", f"{path}/manifest_sha256", "lowercase SHA-256 required")
        if not isinstance(row["resources"], list):
            _fail("E_PLUGIN_LOCK", f"{path}/resources", "resource array required")
        refs = [resource_ref(value, f"{path}/resources/{i}") for i, value in enumerate(row["resources"])]
        if len({(ref["kind"], ref["id"]) for ref in refs}) != len(refs):
            _fail("E_PLUGIN_LOCK", f"{path}/resources", "duplicate resource identity")
    expected = dict(lock); supplied = expected.pop("lock_sha256")
    if supplied != digest(expected):
        _fail("E_PLUGIN_LOCK_DRIFT", "/lock_sha256", "lock bytes do not match")
    if manifests is not None:
        if not isinstance(manifests, Mapping):
            _fail("E_PLUGIN_LOCK_BINDING", "/plugins", "manifest registry required")
        normalized = {name: validate_manifest(value) for name, value in manifests.items()}
        resolve_plugins(normalized, list(normalized))
        if {row["plugin_id"] for row in lock["plugins"]} != set(normalized):
            _fail("E_PLUGIN_LOCK_BINDING", "/plugins", "lock plugin set does not match manifests")
        for row in lock["plugins"]:
            manifest = normalized[row["plugin_id"]]
            if row["version"] != manifest["version"] or row["manifest_sha256"] != digest(manifest) or row["resources"] != sorted(manifest.get("resources", []), key=lambda x: (x["kind"], x["id"])):
                _fail("E_PLUGIN_LOCK_BINDING", f"/plugins/{row['plugin_id']}", "lock is not bound to manifest bytes")
    return copy.deepcopy(dict(lock))


def check_permission_intersection(manifest: Mapping[str, Any], *, allowed_permissions: Sequence[str],
                                  platform_name: str | None = None) -> Dict[str, Any]:
    """Return a conservative offline policy result for one plugin.

    A manifest can describe required permissions and supported platforms, but
    it cannot grant either.  The caller supplies the already-authorized
    intersection; a missing permission or platform keeps the plugin blocked.
    """
    normalized = validate_manifest(manifest)
    if not isinstance(allowed_permissions, Sequence) or isinstance(allowed_permissions, (str, bytes)):
        _fail("E_PLUGIN_POLICY", "/allowed_permissions", "permission list required")
    if any(not isinstance(value, str) or not value for value in allowed_permissions):
        _fail("E_PLUGIN_POLICY", "/allowed_permissions", "permission list must contain non-empty strings")
    allowed = set(allowed_permissions)
    required = set(normalized.get("permissions", []))
    missing = sorted(required - allowed)
    supported = normalized.get("platforms", [])
    platform_blocked = platform_name is not None and bool(supported) and platform_name not in supported
    return {"plugin_id": normalized["plugin_id"], "required_permissions": sorted(required),
            "missing_permissions": missing, "platform": platform_name,
            "platform_blocked": platform_blocked,
            "status": "READY" if not missing and not platform_blocked else "BLOCKED",
            "dispatch_eligibility": "not_evaluated"}


__all__ = ["PluginError", "build_lock", "canonical_bytes", "check_permission_intersection", "digest", "resolve_plugins", "resource_ref", "validate_lock", "validate_manifest"]
