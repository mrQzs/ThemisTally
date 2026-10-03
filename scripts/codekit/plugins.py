"""Strict offline plugin manifest and content-lock validation."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import posixpath
import ntpath
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Sequence, Tuple


VERSION_RE = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
PLUGIN_ID = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
# These names identify a moving reference rather than an immutable plugin
# identity.  They are rejected at every plugin boundary, including registry
# keys, dependency names and lock rows.
MUTABLE_ALIASES = frozenset({"latest", "head", "current", "stable", "default", "main", "master", "dev", "tip"})
MAX_DEPTH = 64
MAX_ARRAY_ITEMS = 512
MAX_BYTES = 1_048_576
MAX_SAFE_INTEGER = 2**53 - 1


class PluginError(ValueError):
    def __init__(self, code: str, path: str, message: str):
        self.code, self.path = code, path
        super().__init__(f"{code} at {path}: {message}")


def _fail(code: str, path: str, message: str) -> None:
    raise PluginError(code, path, message)


def _strict_json(value: Any, *, path: str = "/", depth: int = 0,
                 active: set[int] | None = None) -> None:
    if depth > MAX_DEPTH:
        _fail("E_PLUGIN_JSON", path, "maximum JSON depth exceeded")
    if value is None or type(value) is bool:
        return
    if type(value) is int:
        if abs(value) > MAX_SAFE_INTEGER:
            _fail("E_PLUGIN_JSON", path, "integer exceeds exact JSON range")
        return
    if type(value) is float:
        if not math.isfinite(value):
            _fail("E_PLUGIN_JSON", path, "finite JSON number required")
        return
    if type(value) is str:
        if any(ord(ch) < 0x20 or ord(ch) == 0x7F or 0xD800 <= ord(ch) <= 0xDFFF for ch in value):
            _fail("E_PLUGIN_JSON", path, "safe Unicode text required")
        return
    if type(value) not in (dict, list):
        _fail("E_PLUGIN_JSON", path, "strict JSON value required")
    if active is None:
        active = set()
    marker = id(value)
    if marker in active:
        _fail("E_PLUGIN_JSON", path, "cyclic JSON value")
    active.add(marker)
    try:
        if type(value) is dict:
            for key, child in value.items():
                if type(key) is not str:
                    _fail("E_PLUGIN_JSON", path, "string object keys required")
                if any(ord(ch) < 0x20 or ord(ch) == 0x7F or 0xD800 <= ord(ch) <= 0xDFFF for ch in key):
                    _fail("E_PLUGIN_JSON", path, "safe Unicode object keys required")
                _strict_json(child, path=f"{path}{key}/", depth=depth + 1, active=active)
        else:
            if len(value) > MAX_ARRAY_ITEMS:
                _fail("E_PLUGIN_SCHEMA", path, "array exceeds limit")
            for index, child in enumerate(value):
                _strict_json(child, path=f"{path}{index}/", depth=depth + 1, active=active)
    finally:
        active.remove(marker)


def canonical_bytes(value: Any) -> bytes:
    _strict_json(value)
    try:
        raw = (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise PluginError("E_PLUGIN_JSON", "/", str(exc)) from exc
    if len(raw) > MAX_BYTES:
        _fail("E_PLUGIN_SCHEMA", "/", "canonical plugin record exceeds byte limit")
    return raw


def digest(value: Any) -> str:
    return hashlib.sha256(value if isinstance(value, bytes) else canonical_bytes(value)).hexdigest()


def _identifier(value: Any, path: str) -> None:
    if type(value) is not str or not PLUGIN_ID.fullmatch(value) or value.lower() in MUTABLE_ALIASES:
        _fail("E_PLUGIN_IDENTITY", path, "lowercase plugin id required")


def _exact_version(value: Any, path: str) -> None:
    if type(value) is not str or not VERSION_RE.fullmatch(value):
        _fail("E_PLUGIN_VERSION", path, "exact semantic version required")


def _contains_mutable_alias(value: str) -> bool:
    lowered = value.lower()
    return any(re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", lowered) for alias in MUTABLE_ALIASES)


def _sequence(value: Any, path: str, message: str) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        _fail("E_PLUGIN_SCHEMA", path, message)
    return list(value)


def _strings(value: Any, path: str) -> None:
    if not isinstance(value, list) or len(value) > MAX_ARRAY_ITEMS or any(
            type(x) is not str or not x or len(x) > 256
            or any(ord(ch) < 0x20 or ord(ch) == 0x7F or 0xD800 <= ord(ch) <= 0xDFFF for ch in x)
            for x in value):
        _fail("E_PLUGIN_SCHEMA", path, "unique non-empty string array required")
    if len(set(value)) != len(value):
        _fail("E_PLUGIN_SCHEMA", path, "duplicate value")


def resource_ref(value: Any, path: str) -> Dict[str, str]:
    if not isinstance(value, dict) or set(value) != {"kind", "id", "path", "sha256"}:
        _fail("E_PLUGIN_RESOURCE", path, "closed ResourceRef required")
    for key in ("kind", "id", "path"):
        if type(value[key]) is not str or not value[key] or any(
                ord(ch) < 0x20 or ord(ch) == 0x7F or 0xD800 <= ord(ch) <= 0xDFFF
                for ch in value[key]):
            _fail("E_PLUGIN_RESOURCE", f"{path}/{key}", "non-empty string required")
    # Resource paths are persisted in lock bytes.  Normalize Unicode before
    # applying traversal checks so canonically equivalent names cannot bypass
    # the same-path policy on a platform whose filesystem normalizes names.
    kind = unicodedata.normalize("NFC", value["kind"])
    resource_id = unicodedata.normalize("NFC", value["id"])
    name = unicodedata.normalize("NFC", value["path"].replace("\\", "/"))
    if name.startswith("/") or ntpath.splitdrive(name)[0] or name.startswith("./") or any(part in {"", ".", ".."} for part in name.split("/")) or any(ord(ch) < 32 or ord(ch) == 127 for ch in name):
        _fail("E_PLUGIN_PATH", f"{path}/path", "absolute and traversal paths are forbidden")
    if not isinstance(value["sha256"], str) or not HEX64.fullmatch(value["sha256"]):
        _fail("E_PLUGIN_RESOURCE", f"{path}/sha256", "lowercase SHA-256 required")
    return {"kind": kind, "id": resource_id, "path": name, "sha256": value["sha256"]}


def _resource_path_key(value: Mapping[str, str]) -> str:
    """Return the conservative cross-platform identity of a resource path.

    Windows and macOS commonly compare paths case-insensitively (and macOS
    may normalize Unicode).  Treating aliases as distinct resources lets two
    plugin declarations silently target one file and makes lock consumption
    depend on traversal order.  The path itself remains case-preserving in
    the manifest; this key is only used for collision detection.
    """
    return unicodedata.normalize("NFC", value["path"]).casefold()


def _reject_resource_path_collisions(refs: Sequence[Mapping[str, str]], path: str) -> None:
    seen: Dict[str, int] = {}
    for index, ref in enumerate(refs):
        key = _resource_path_key(ref)
        previous = seen.get(key)
        if previous is not None:
            _fail("E_PLUGIN_RESOURCE", f"{path}/{index}/path",
                  f"resource path aliases entry {previous}")
        seen[key] = index


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
    _exact_version(manifest["version"], "/version")
    if _contains_mutable_alias(manifest["api_version"]):
        _fail("E_PLUGIN_VERSION", "/version", "mutable aliases are forbidden")
    for field in ("roles", "capabilities", "depends_on", "conflicts", "platforms", "permissions"):
        if field in manifest:
            _strings(manifest[field], f"/{field}")
    for field in ("depends_on", "conflicts"):
        for index, name in enumerate(manifest.get(field, [])):
            _identifier(name, f"/{field}/{index}")
    resources = manifest.get("resources", [])
    if not isinstance(resources, list) or len(resources) > MAX_ARRAY_ITEMS:
        _fail("E_PLUGIN_SCHEMA", "/resources", "resource array required")
    refs = [resource_ref(value, f"/resources/{i}") for i, value in enumerate(resources)]
    if len({(x["kind"], x["id"]) for x in refs}) != len(refs):
        _fail("E_PLUGIN_RESOURCE", "/resources", "duplicate resource identity")
    _reject_resource_path_collisions(refs, "/resources")
    entrypoints = manifest.get("entrypoints", [])
    _strings(entrypoints, "/entrypoints")
    checks = manifest.get("checks", [])
    if not isinstance(checks, list) or any(not isinstance(x, dict) for x in checks):
        _fail("E_PLUGIN_SCHEMA", "/checks", "check descriptor array required")
    for i, check in enumerate(checks):
        if (set(check) != {"id", "command", "deterministic"} or type(check.get("id")) is not str
                or not check["id"] or len(check["id"]) > 256
                or any(ord(ch) < 0x20 or ord(ch) == 0x7F or 0xD800 <= ord(ch) <= 0xDFFF for ch in check["id"])
                or not isinstance(check.get("command"), list) or not check["command"]
                or len(check["command"]) > MAX_ARRAY_ITEMS
                or any(type(arg) is not str or not arg or len(arg) > 4096
                       or any(ord(ch) < 0x20 or ord(ch) == 0x7F or 0xD800 <= ord(ch) <= 0xDFFF for ch in arg)
                       for arg in check["command"])
                or type(check.get("deterministic")) is not bool):
            _fail("E_PLUGIN_CHECK", f"/checks/{i}", "closed id/command/deterministic check required")
        flat = " ".join(str(x) for x in check["command"])
        if any(token in flat.lower() for token in ("importlib", "__import__", "eval(", "exec(", "http://", "https://")) or _contains_mutable_alias(flat):
            _fail("E_PLUGIN_CHECK", f"/checks/{i}/command", "dynamic import, network and mutable alias are forbidden")
    if len({check["id"] for check in checks}) != len(checks):
        _fail("E_PLUGIN_CHECK", "/checks", "duplicate check id")
    if not manifest["roles"] and (not checks or any(not check["deterministic"] for check in checks)):
        _fail("E_PLUGIN_CHECK", "/checks", "role-free plugins require explicit deterministic checks")
    normalized = copy.deepcopy(dict(manifest))
    # ResourceRef paths are part of the identity bytes.  Preserve the
    # normalized slash form returned by resource_ref before hashing and
    # returning the manifest; otherwise a lock could bind one spelling while
    # consumers use another.
    normalized["resources"] = refs
    canonical_bytes(normalized)
    return normalized


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
    # A resolved set has one namespace.  Even when resource IDs differ, two
    # case/Unicode-equivalent paths would make consumption order-dependent on
    # Windows/macOS.  Reject the combination unless a future schema explicitly
    # introduces a shared-resource namespace.
    paths: Dict[str, tuple[str, int]] = {}
    for manifest in result:
        for index, ref in enumerate(manifest.get("resources", [])):
            key = _resource_path_key(ref)
            if key in paths:
                other_plugin, other_index = paths[key]
                _fail("E_PLUGIN_RESOURCE", f"/plugins/{manifest['plugin_id']}/resources/{index}/path",
                      f"resource path collides with {other_plugin}/resources/{other_index}")
            paths[key] = (manifest["plugin_id"], index)
    return tuple(result)


def build_lock(manifests: Sequence[Mapping[str, Any]], *, compiler_sha256: str, generation: int = 1) -> Dict[str, Any]:
    if not isinstance(compiler_sha256, str) or not HEX64.fullmatch(compiler_sha256) or type(generation) is not int or generation < 1:
        _fail("E_PLUGIN_LOCK", "/", "compiler hash and positive generation required")
    values = _sequence(manifests, "/manifests", "manifest sequence required")
    normalized_manifests = [validate_manifest(x) for x in values]
    identifiers = [item["plugin_id"] for item in normalized_manifests]
    if len(set(identifiers)) != len(identifiers):
        _fail("E_PLUGIN_LOCK", "/manifests", "duplicate plugin id")
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
    plugin_order = []
    normalized_rows = []
    resource_paths: Dict[str, tuple[str, int]] = {}
    for index, row in enumerate(lock["plugins"]):
        path = f"/plugins/{index}"
        if not isinstance(row, dict) or set(row) != {"plugin_id", "version", "manifest_sha256", "resources"}:
            _fail("E_PLUGIN_LOCK", path, "closed plugin lock row required")
        _identifier(row["plugin_id"], f"{path}/plugin_id")
        if row["plugin_id"] in seen:
            _fail("E_PLUGIN_LOCK", path, "duplicate plugin id")
        seen.add(row["plugin_id"])
        plugin_order.append(row["plugin_id"])
        if not isinstance(row["version"], str) or not VERSION_RE.fullmatch(row["version"]):
            _fail("E_PLUGIN_LOCK", f"{path}/version", "exact semantic version required")
        if not isinstance(row["manifest_sha256"], str) or not HEX64.fullmatch(row["manifest_sha256"]):
            _fail("E_PLUGIN_LOCK", f"{path}/manifest_sha256", "lowercase SHA-256 required")
        if not isinstance(row["resources"], list):
            _fail("E_PLUGIN_LOCK", f"{path}/resources", "resource array required")
        refs = [resource_ref(value, f"{path}/resources/{i}") for i, value in enumerate(row["resources"])]
        if len({(ref["kind"], ref["id"]) for ref in refs}) != len(refs):
            _fail("E_PLUGIN_LOCK", f"{path}/resources", "duplicate resource identity")
        _reject_resource_path_collisions(refs, f"{path}/resources")
        for resource_index, ref in enumerate(refs):
            key = _resource_path_key(ref)
            if key in resource_paths:
                other_plugin, other_index = resource_paths[key]
                _fail("E_PLUGIN_RESOURCE", f"{path}/resources/{resource_index}/path",
                      f"resource path collides with {other_plugin}/resources/{other_index}")
            resource_paths[key] = (row["plugin_id"], resource_index)
        if [(ref["kind"], ref["id"]) for ref in refs] != sorted((ref["kind"], ref["id"]) for ref in refs):
            _fail("E_PLUGIN_LOCK", f"{path}/resources", "resources must be in canonical order")
        normalized_rows.append({"plugin_id": row["plugin_id"], "version": row["version"],
                                "manifest_sha256": row["manifest_sha256"],
                                "resources": refs})
    if plugin_order != sorted(plugin_order):
        _fail("E_PLUGIN_LOCK", "/plugins", "plugins must be in canonical order")
    expected = {"record_type": lock["record_type"], "schema_version": lock["schema_version"],
                "generation": lock["generation"], "compiler_sha256": lock["compiler_sha256"],
                "plugins": normalized_rows}
    supplied = lock["lock_sha256"]
    if supplied != digest(expected):
        _fail("E_PLUGIN_LOCK_DRIFT", "/lock_sha256", "lock bytes do not match")
    if manifests is not None:
        if not isinstance(manifests, Mapping):
            _fail("E_PLUGIN_LOCK_BINDING", "/plugins", "manifest registry required")
        normalized = {name: validate_manifest(value) for name, value in manifests.items()}
        resolve_plugins(normalized, list(normalized))
        if {row["plugin_id"] for row in lock["plugins"]} != set(normalized):
            _fail("E_PLUGIN_LOCK_BINDING", "/plugins", "lock plugin set does not match manifests")
        for row in normalized_rows:
            manifest = normalized[row["plugin_id"]]
            if row["version"] != manifest["version"] or row["manifest_sha256"] != digest(manifest) or row["resources"] != sorted(manifest.get("resources", []), key=lambda x: (x["kind"], x["id"])):
                _fail("E_PLUGIN_LOCK_BINDING", f"/plugins/{row['plugin_id']}", "lock is not bound to manifest bytes")
    result = copy.deepcopy(dict(lock))
    result["plugins"] = normalized_rows
    return result


def check_permission_intersection(manifest: Mapping[str, Any], *, allowed_permissions: Sequence[str],
                                  platform_name: str | None = None) -> Dict[str, Any]:
    """Return a conservative offline policy result for one plugin.

    A manifest can describe required permissions and supported platforms, but
    it cannot grant either.  The caller supplies the already-authorized
    intersection; a missing permission or platform keeps the plugin blocked.
    """
    normalized = validate_manifest(manifest)
    if not isinstance(allowed_permissions, Sequence) or isinstance(allowed_permissions, (str, bytes, bytearray)):
        _fail("E_PLUGIN_POLICY", "/allowed_permissions", "permission list required")
    if any(not isinstance(value, str) or not value for value in allowed_permissions):
        _fail("E_PLUGIN_POLICY", "/allowed_permissions", "permission list must contain non-empty strings")
    if len(set(allowed_permissions)) != len(allowed_permissions):
        _fail("E_PLUGIN_POLICY", "/allowed_permissions", "permission list must be unique")
    if platform_name is not None and (not isinstance(platform_name, str) or not platform_name):
        _fail("E_PLUGIN_POLICY", "/platform_name", "platform name must be non-empty text")
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
