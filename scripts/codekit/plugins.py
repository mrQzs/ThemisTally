"""Strict offline plugin manifest and content-lock validation."""

from __future__ import annotations

import copy
import hashlib
import json
import posixpath
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Sequence, Tuple


VERSION_RE = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


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


def resource_ref(value: Any, path: str) -> Dict[str, str]:
    if not isinstance(value, dict) or set(value) != {"kind", "id", "path", "sha256"}:
        _fail("E_PLUGIN_RESOURCE", path, "closed ResourceRef required")
    for key in ("kind", "id", "path"):
        if not isinstance(value[key], str) or not value[key]:
            _fail("E_PLUGIN_RESOURCE", f"{path}/{key}", "non-empty string required")
    name = value["path"].replace("\\", "/")
    if name.startswith("/") or name.startswith("./") or ".." in name.split("/"):
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
    for field in ("record_type", "plugin_id", "version", "api_version"):
        if not isinstance(manifest.get(field), str) or not manifest[field]:
            _fail("E_PLUGIN_SCHEMA", f"/{field}", "non-empty string required")
    if manifest["record_type"] != "builtin-task-plugin-manifest" or manifest["schema_version"] != 1:
        _fail("E_PLUGIN_VERSION", "/record_type", "manifest schema version 1 required")
    if not VERSION_RE.fullmatch(manifest["version"]):
        _fail("E_PLUGIN_VERSION", "/version", "exact semantic version required")
    if "latest" in manifest["version"].lower() or "latest" in manifest["api_version"].lower():
        _fail("E_PLUGIN_VERSION", "/version", "mutable aliases are forbidden")
    for field in ("roles", "capabilities", "depends_on", "conflicts", "platforms", "permissions"):
        if field in manifest and (not isinstance(manifest[field], list) or any(not isinstance(x, str) or not x for x in manifest[field])):
            _fail("E_PLUGIN_SCHEMA", f"/{field}", "unique string array required")
    if len(set(manifest.get("roles", []))) != len(manifest.get("roles", [])):
        _fail("E_PLUGIN_SCHEMA", "/roles", "duplicate role")
    resources = manifest.get("resources", [])
    if not isinstance(resources, list):
        _fail("E_PLUGIN_SCHEMA", "/resources", "resource array required")
    refs = [resource_ref(value, f"/resources/{i}") for i, value in enumerate(resources)]
    if len({(x["kind"], x["id"]) for x in refs}) != len(refs):
        _fail("E_PLUGIN_RESOURCE", "/resources", "duplicate resource identity")
    entrypoints = manifest.get("entrypoints", [])
    if not isinstance(entrypoints, list) or any(not isinstance(x, str) or not x for x in entrypoints):
        _fail("E_PLUGIN_SCHEMA", "/entrypoints", "entrypoint array required")
    checks = manifest.get("checks", [])
    if not isinstance(checks, list) or any(not isinstance(x, dict) for x in checks):
        _fail("E_PLUGIN_SCHEMA", "/checks", "check descriptor array required")
    for i, check in enumerate(checks):
        if set(check) - {"id", "command", "deterministic"} or not isinstance(check.get("id"), str) or not isinstance(check.get("command"), list):
            _fail("E_PLUGIN_CHECK", f"/checks/{i}", "closed id/command/deterministic check required")
        flat = " ".join(str(x) for x in check["command"])
        if any(token in flat.lower() for token in ("importlib", "__import__", "eval(", "exec(", "http://", "https://", "latest")):
            _fail("E_PLUGIN_CHECK", f"/checks/{i}/command", "dynamic import, network and mutable alias are forbidden")
    return copy.deepcopy(dict(manifest))


def resolve_plugins(manifests: Mapping[str, Mapping[str, Any]], enabled: Sequence[str]) -> Tuple[Dict[str, Any], ...]:
    normalized = {name: validate_manifest(value) for name, value in manifests.items()}
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
    if not HEX64.fullmatch(compiler_sha256) or type(generation) is not int or generation < 1:
        _fail("E_PLUGIN_LOCK", "/", "compiler hash and positive generation required")
    rows = []
    for manifest in sorted((validate_manifest(x) for x in manifests), key=lambda x: x["plugin_id"]):
        rows.append({"plugin_id": manifest["plugin_id"], "version": manifest["version"], "manifest_sha256": digest(manifest),
                     "resources": sorted(manifest.get("resources", []), key=lambda x: (x["kind"], x["id"]))})
    lock = {"record_type": "plugin-lock", "schema_version": 1, "generation": generation,
            "compiler_sha256": compiler_sha256, "plugins": rows}
    lock["lock_sha256"] = digest(lock)
    return lock


def validate_lock(lock: Mapping[str, Any]) -> Dict[str, Any]:
    required = {"record_type", "schema_version", "generation", "compiler_sha256", "plugins", "lock_sha256"}
    if not isinstance(lock, dict) or set(lock) != required:
        _fail("E_PLUGIN_LOCK", "/", "closed plugin lock required")
    if lock["record_type"] != "plugin-lock" or lock["schema_version"] != 1 or type(lock["generation"]) is not int or lock["generation"] < 1:
        _fail("E_PLUGIN_LOCK", "/", "invalid lock header")
    expected = dict(lock); supplied = expected.pop("lock_sha256")
    if supplied != digest(expected):
        _fail("E_PLUGIN_LOCK_DRIFT", "/lock_sha256", "lock bytes do not match")
    return copy.deepcopy(dict(lock))


__all__ = ["PluginError", "build_lock", "canonical_bytes", "digest", "resolve_plugins", "resource_ref", "validate_lock", "validate_manifest"]
