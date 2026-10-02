"""Strict, offline configuration/profile resolution for Code-Kit v2.

This module owns only declaration parsing and semantic snapshot construction.
It never probes a CLI, reads credential values, starts a process, or grants an
execution/approval decision.  Runtime adapters and the 03/05/07 gates consume
the returned immutable snapshot and perform their own currentness checks.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import ntpath
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple


ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
NOTE_RE = re.compile(r"^_[A-Za-z][A-Za-z0-9_]{0,63}$")
RESERVED_NOTES = {"_model", "_permissions", "_policies", "_command", "_schema_version"}
ROLES = ("supervisor", "planner", "executor", "observer")
LOCAL_TOP_LEVEL = {"schema_version", "runtimes", "platforms"}
LOCAL_RUNTIME_KEYS = {"executable_by_platform"}
LOCAL_PLATFORM_KEYS = {"shell_executable", "tools"}


class ConfigError(ValueError):
    """Stable configuration error family used by callers and diagnostics."""

    def __init__(self, code: str, path: str, message: str, *, retryable: bool = False):
        self.code = code
        self.path = path
        self.retryable = retryable
        super().__init__(f"{code} at {path}: {message}")

    def as_dict(self) -> Dict[str, Any]:
        return {"code": self.code, "path": self.path, "message": str(self), "retryable": self.retryable}


def _fail(code: str, path: str, message: str) -> None:
    raise ConfigError(code, path, message)


def _duplicate_pairs(pairs: Iterable[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail("E_JSON_DUPLICATE", "/" + str(key), "duplicate object key")
        result[key] = value
    return result


def _reject_constant(value: str) -> Any:
    _fail("E_JSON_NUMBER", "/", f"non-finite number {value} is forbidden")


def load_strict_json(raw: bytes | str) -> Dict[str, Any]:
    """Parse UTF-8 JSON with duplicate-key and non-finite-number rejection."""

    if isinstance(raw, bytes):
        if raw.startswith(b"\xef\xbb\xbf"):
            raise ConfigError("E_JSON_ENCODING", "/", "UTF-8 BOM is forbidden")
        try:
            raw = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ConfigError("E_JSON_ENCODING", "/", "configuration must be UTF-8") from exc
    if len(raw.encode("utf-8")) > 1_048_576:
        _fail("E_JSON_SIZE", "/", "configuration exceeds one MiB")
    if raw.startswith("\ufeff"):
        _fail("E_JSON_ENCODING", "/", "UTF-8 BOM is forbidden")
    try:
        value = json.loads(raw, object_pairs_hook=_duplicate_pairs, parse_constant=_reject_constant)
    except ConfigError:
        raise
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ConfigError("E_JSON_SYNTAX", "/", str(exc)) from exc
    if not isinstance(value, dict):
        _fail("E_CFG_SCHEMA", "/", "top-level configuration must be an object")
    def check_depth(item: Any, depth: int = 0) -> None:
        if depth > 64:
            _fail("E_JSON_DEPTH", "/", "configuration nesting exceeds 64 levels")
        if isinstance(item, float) and not math.isfinite(item):
            _fail("E_JSON_NUMBER", "/", "non-finite number is forbidden")
        if isinstance(item, dict):
            for child in item.values(): check_depth(child, depth + 1)
        elif isinstance(item, list):
            for child in item: check_depth(child, depth + 1)
    check_depth(value)
    if "schema_version" in value and type(value["schema_version"]) is bool:
        _fail("E_CFG_VERSION", "/schema_version", "boolean is not a schema version")
    return value


def canonical_json_bytes(value: Any) -> bytes:
    """Return the v2 semantic snapshot encoding (UTF-8, sorted, newline)."""

    try:
        return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ConfigError("E_JSON_NUMBER", "/", str(exc)) from exc


def _object(value: Any, path: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        _fail("E_CFG_SCHEMA", path, "object required")
    return value


def _string(value: Any, path: str, *, nonempty: bool = True) -> str:
    if not isinstance(value, str) or (nonempty and not value):
        _fail("E_CFG_SCHEMA", path, "non-empty string required")
    return value


def _id(value: Any, path: str) -> str:
    value = _string(value, path)
    if not ID_RE.fullmatch(value):
        _fail("E_CFG_SCHEMA", path, "invalid stable identifier")
    return value


def _string_list(value: Any, path: str, *, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list) or (nonempty and not value):
        _fail("E_CFG_SCHEMA", path, "string array required")
    result = []
    for index, item in enumerate(value):
        result.append(_string(item, f"{path}/{index}"))
    return result


def _check_notes(obj: Mapping[str, Any], path: str, allowed: set[str]) -> None:
    for key, value in obj.items():
        if key.startswith("_"):
            if key in RESERVED_NOTES or not NOTE_RE.fullmatch(key) or key not in allowed:
                _fail("E_CFG_NOTE_SHADOW", f"{path}/{key}", "unregistered or semantic note name")
            if not isinstance(value, str) or len(value) > 4096:
                _fail("E_CFG_SCHEMA", f"{path}/{key}", "note must be a string up to 4096 characters")


@dataclass(frozen=True)
class AdapterDescriptor:
    adapter_id: str
    descriptor_version: str
    capabilities: Tuple[str, ...] = ()
    model_ids: Tuple[str, ...] = ()
    option_keys: Tuple[str, ...] = ()
    provider: Optional[str] = None
    deployment: Optional[str] = None
    descriptor_sha256: Optional[str] = None

    def validate_model(self, model: Mapping[str, Any], path: str) -> None:
        _object(model, path)
        model_id = _string(model.get("id"), f"{path}/id")
        if self.model_ids and model_id not in self.model_ids:
            _fail("E_CFG_ADAPTER_SCHEMA", f"{path}/id", "model is not in the registered adapter descriptor")
        unknown = set(model) - {"id", "provider", "deployment", "region"}
        if unknown:
            _fail("E_CFG_ADAPTER_SCHEMA", path, f"unknown model fields: {sorted(unknown)}")

    def validate_options(self, options: Mapping[str, Any], path: str) -> None:
        if not isinstance(options, dict):
            _fail("E_CFG_ADAPTER_SCHEMA", path, "options must be an object")
        if self.option_keys:
            unknown = set(options) - set(self.option_keys)
            if unknown:
                _fail("E_CFG_ADAPTER_SCHEMA", path, f"unknown option fields: {sorted(unknown)}")


class AdapterRegistry:
    def __init__(self, descriptors: Iterable[AdapterDescriptor] = ()):
        self._items: dict[str, AdapterDescriptor] = {}
        for descriptor in descriptors:
            self.register(descriptor)

    def register(self, descriptor: AdapterDescriptor) -> None:
        if descriptor.adapter_id in self._items:
            _fail("E_CFG_ADAPTER", f"/runtimes/{descriptor.adapter_id}/adapter", "duplicate adapter id")
        self._items[descriptor.adapter_id] = descriptor

    def require(self, adapter_id: str, path: str) -> AdapterDescriptor:
        item = self._items.get(adapter_id)
        if item is None:
            _fail("E_CFG_ADAPTER", path, "adapter is not registered")
        return item


def _validate_runtime(runtime_id: str, runtime: Any, registry: AdapterRegistry) -> None:
    path = f"/runtimes/{runtime_id}"
    obj = _object(runtime, path)
    _check_notes(obj, path, {"_description"})
    allowed = {"adapter", "command", "command_by_platform", "_description"}
    unknown = set(obj) - allowed
    if unknown:
        _fail("E_CFG_UNKNOWN_FIELD", path, f"unknown runtime fields: {sorted(unknown)}")
    adapter_id = _id(obj.get("adapter"), f"{path}/adapter")
    descriptor = registry.require(adapter_id, f"{path}/adapter")
    _string_list(obj.get("command"), f"{path}/command", nonempty=True)
    branches = obj.get("command_by_platform", {})
    if not isinstance(branches, dict):
        _fail("E_CFG_SCHEMA", f"{path}/command_by_platform", "platform map required")
    for platform, command in branches.items():
        _id(platform, f"{path}/command_by_platform/{platform}")
        _string_list(command, f"{path}/command_by_platform/{platform}", nonempty=True)
    if descriptor.adapter_id != adapter_id:
        _fail("E_CFG_ADAPTER", f"{path}/adapter", "registry identity mismatch")


def _validate_profile(profile_id: str, profile: Any, runtimes: Mapping[str, Any], registry: AdapterRegistry) -> None:
    path = f"/profiles/{profile_id}"
    obj = _object(profile, path)
    _check_notes(obj, path, {"_description"})
    allowed = {"runtime", "model", "options", "credential_refs", "_description"}
    unknown = set(obj) - allowed
    if unknown:
        _fail("E_CFG_UNKNOWN_FIELD", path, f"unknown profile fields: {sorted(unknown)}")
    runtime_id = _id(obj.get("runtime"), f"{path}/runtime")
    if runtime_id not in runtimes:
        _fail("E_CFG_REFERENCE", f"{path}/runtime", "runtime does not exist")
    runtime = runtimes[runtime_id]
    descriptor = registry.require(runtime["adapter"], f"/runtimes/{runtime_id}/adapter")
    descriptor.validate_model(_object(obj.get("model"), f"{path}/model"), f"{path}/model")
    options = obj.get("options", {})
    descriptor.validate_options(_object(options, f"{path}/options"), f"{path}/options")
    refs = obj.get("credential_refs", [])
    if not isinstance(refs, list):
        _fail("E_CFG_SCHEMA", f"{path}/credential_refs", "array required")
    seen = set()
    for index, ref in enumerate(refs):
        ref_obj = _object(ref, f"{path}/credential_refs/{index}")
        if set(ref_obj) - {"kind", "name", "binding"}:
            _fail("E_CFG_UNKNOWN_FIELD", f"{path}/credential_refs/{index}", "unknown credential reference field")
        name = _string(ref_obj.get("name"), f"{path}/credential_refs/{index}/name")
        if name in seen:
            _fail("E_CFG_SCHEMA", f"{path}/credential_refs/{index}/name", "duplicate credential reference")
        seen.add(name)
        _string(ref_obj.get("kind"), f"{path}/credential_refs/{index}/kind")


def validate_config(config: Mapping[str, Any], registry: AdapterRegistry) -> Dict[str, Any]:
    """Validate and return a detached v2 declaration."""

    root = _object(config, "/")
    allowed = {"schema_version", "runtimes", "profiles", "roles", "policies", "platforms"}
    allowed.add("_description")
    _check_notes(root, "/", {"_description"})
    unknown = {key for key in root if key not in allowed}
    if unknown:
        _fail("E_CFG_UNKNOWN_FIELD", "/", f"unknown fields: {sorted(unknown)}")
    if type(root.get("schema_version")) is not int or root.get("schema_version") != 2:
        _fail("E_CFG_VERSION", "/schema_version", "v2 requires integer schema_version 2")
    runtimes = _object(root.get("runtimes"), "/runtimes")
    profiles = _object(root.get("profiles"), "/profiles")
    roles = _object(root.get("roles"), "/roles")
    if not runtimes or not profiles:
        _fail("E_CFG_SCHEMA", "/", "at least one runtime and profile are required")
    for runtime_id, runtime in runtimes.items():
        _id(runtime_id, f"/runtimes/{runtime_id}")
        _validate_runtime(runtime_id, runtime, registry)
    for profile_id, profile in profiles.items():
        _id(profile_id, f"/profiles/{profile_id}")
        _validate_profile(profile_id, profile, runtimes, registry)
    for role, binding in roles.items():
        if role not in ROLES:
            _fail("E_CFG_SCHEMA", f"/roles/{role}", "unknown role")
        obj = _object(binding, f"/roles/{role}")
        _check_notes(obj, f"/roles/{role}", {"_description"})
        if obj.get("mode") == "disabled":
            if set(obj) - {"mode", "_description"}:
                _fail("E_CFG_SCHEMA", f"/roles/{role}", "disabled role cannot carry a profile")
            continue
        if role == "supervisor" and obj.get("mode") == "current_session":
            continue
        profile_id = _id(obj.get("profile"), f"/roles/{role}/profile")
        if profile_id not in profiles:
            _fail("E_CFG_REFERENCE", f"/roles/{role}/profile", "profile does not exist")
    policies = root.get("policies", {})
    if policies is not None and not isinstance(policies, dict):
        _fail("E_CFG_SCHEMA", "/policies", "object required")
    platforms = root.get("platforms", {})
    if platforms is not None and not isinstance(platforms, dict):
        _fail("E_CFG_SCHEMA", "/platforms", "object required")
    return copy.deepcopy(dict(root))


def _policy(value: Any, path: str) -> Dict[str, Any]:
    if value is None:
        return {}
    obj = _object(value, path)
    allowed = {"allowed_models", "role_profiles", "required_capabilities", "environment_allow_names", "protected_paths", "approval_required"}
    unknown = set(obj) - allowed
    if unknown:
        _fail("E_CFG_POLICY", path, f"unknown policy fields: {sorted(unknown)}")
    out: Dict[str, Any] = {}
    if "allowed_models" in obj:
        models = obj["allowed_models"]
        if not isinstance(models, list): _fail("E_CFG_POLICY", f"{path}/allowed_models", "array required")
        rows = []
        for index, item in enumerate(models):
            row = _object(item, f"{path}/allowed_models/{index}")
            if set(row) - {"adapter", "id", "provider", "deployment"} or "adapter" not in row or "id" not in row:
                _fail("E_CFG_POLICY", f"{path}/allowed_models/{index}", "adapter and model id required")
            normalized = {key: _string(row[key], f"{path}/allowed_models/{index}/{key}") for key in row}
            rows.append(normalized)
        out["allowed_models"] = rows
    for field in ("role_profiles", "required_capabilities"):
        if field in obj:
            mapping = _object(obj[field], f"{path}/{field}"); result = {}
            for key, values in mapping.items():
                if key not in ROLES: _fail("E_CFG_POLICY", f"{path}/{field}/{key}", "unknown role")
                result[key] = _string_list(values, f"{path}/{field}/{key}")
            out[field] = result
    for field in ("environment_allow_names", "protected_paths"):
        if field in obj:
            values = _string_list(obj[field], f"{path}/{field}")
            for index, value in enumerate(values):
                if field == "protected_paths" and (value.startswith("/") or ".." in value.replace("\\", "/").split("/")):
                    _fail("E_CFG_POLICY", f"{path}/{field}/{index}", "protected path must remain relative")
            out[field] = values
    if "approval_required" in obj:
        if type(obj["approval_required"]) is not bool: _fail("E_CFG_POLICY", f"{path}/approval_required", "boolean required")
        out["approval_required"] = obj["approval_required"]
    return out


def _model_identity(model: Mapping[str, Any], descriptor: AdapterDescriptor) -> Dict[str, str]:
    result = {"adapter": descriptor.adapter_id, "id": str(model["id"])}
    for key in ("provider", "deployment"):
        if key in model: result[key] = str(model[key])
    if descriptor.provider and "provider" not in result: result["provider"] = descriptor.provider
    if descriptor.deployment and "deployment" not in result: result["deployment"] = descriptor.deployment
    return result


def _policy_allows(policy: Mapping[str, Any], *, role: str, profile_id: str, model: Mapping[str, Any], descriptor: AdapterDescriptor,
                   credential_refs: Sequence[Mapping[str, Any]]) -> None:
    if "role_profiles" in policy and profile_id not in policy["role_profiles"].get(role, []):
        _fail("E_CFG_POLICY", f"/policies/role_profiles/{role}", "profile is not allowed for role")
    if "allowed_models" in policy:
        identity = _model_identity(model, descriptor)
        allowed = [{key: row[key] for key in row} for row in policy["allowed_models"]]
        if not any(all(identity.get(key) == value for key, value in row.items()) for row in allowed):
            _fail("E_CFG_POLICY", "/policies/allowed_models", "model identity is not allowed")
    if "required_capabilities" in policy and not set(policy["required_capabilities"].get(role, [])) <= set(descriptor.capabilities):
        _fail("E_CFG_POLICY", f"/policies/required_capabilities/{role}", "adapter capabilities are insufficient")
    if "environment_allow_names" in policy:
        allowed = set(policy["environment_allow_names"])
        if any(ref.get("kind") == "env" and ref.get("name") not in allowed for ref in credential_refs):
            _fail("E_CFG_POLICY", "/policies/environment_allow_names", "credential reference is not allowed")


def _absolute_path(value: Any, path: str, *, platform: Optional[str] = None) -> str:
    value = _string(value, path)
    absolute = ntpath.isabs(value) if platform == "windows" else os.path.isabs(value)
    normalized = ntpath.normpath(value) if platform == "windows" else os.path.normpath(value)
    if not absolute or normalized != value:
        _fail("E_CFG_PATH", path, "local executable override must be normalized absolute path")
    return value


def apply_local_overrides(config: Mapping[str, Any], local: Mapping[str, Any], *, platform: str) -> Dict[str, Any]:
    """Apply only the explicitly permitted local executable/shell patches."""

    result = copy.deepcopy(dict(config))
    obj = _object(local, "/local")
    unknown_top = set(obj) - LOCAL_TOP_LEVEL - {k for k in obj if k.startswith("_")}
    if unknown_top:
        _fail("E_CFG_PATH", "/local", f"local field is not allowed: {sorted(unknown_top)}")
    if "schema_version" in obj and obj["schema_version"] != config.get("schema_version"):
        _fail("E_CFG_VERSION", "/local/schema_version", "local version must match project version")
    if "profiles" in obj or "roles" in obj or "policies" in obj:
        _fail("E_CFG_PATH", "/local", "local cannot alter profiles, roles or policy")
    runtimes = obj.get("runtimes", {})
    if not isinstance(runtimes, dict):
        _fail("E_CFG_PATH", "/local/runtimes", "runtime patch map required")
    for runtime_id, patch in runtimes.items():
        if runtime_id not in result.get("runtimes", {}):
            _fail("E_CFG_REFERENCE", f"/local/runtimes/{runtime_id}", "runtime does not exist")
        patch_obj = _object(patch, f"/local/runtimes/{runtime_id}")
        if set(patch_obj) - LOCAL_RUNTIME_KEYS:
            _fail("E_CFG_PATH", f"/local/runtimes/{runtime_id}", "only executable_by_platform is allowed")
        branches = _object(patch_obj.get("executable_by_platform", {}), f"/local/runtimes/{runtime_id}/executable_by_platform")
        if platform in branches:
            result["runtimes"][runtime_id].setdefault("command_by_platform", {})
            command = list(result["runtimes"][runtime_id]["command_by_platform"].get(platform, result["runtimes"][runtime_id]["command"]))
            command[0] = _absolute_path(branches[platform], f"/local/runtimes/{runtime_id}/executable_by_platform/{platform}", platform=platform)
            result["runtimes"][runtime_id]["command_by_platform"][platform] = command
        if set(branches) - {platform}:
            _fail("E_CFG_PLATFORM", f"/local/runtimes/{runtime_id}/executable_by_platform", "patch target must be the selected platform")
    platforms = obj.get("platforms", {})
    if not isinstance(platforms, dict):
        _fail("E_CFG_PATH", "/local/platforms", "platform patch map required")
    if platform in platforms:
        patch = _object(platforms[platform], f"/local/platforms/{platform}")
        if set(patch) - LOCAL_PLATFORM_KEYS:
            _fail("E_CFG_PATH", f"/local/platforms/{platform}", "unsupported local platform field")
        target = result.setdefault("platforms", {}).setdefault(platform, {})
        if "shell_executable" in patch:
            target["shell_executable"] = _absolute_path(patch["shell_executable"], f"/local/platforms/{platform}/shell_executable", platform=platform)
        if "tools" in patch:
            tools = _object(patch["tools"], f"/local/platforms/{platform}/tools")
            target_tools = target.setdefault("tools", {})
            for tool_id, executable in tools.items():
                if tool_id not in target_tools:
                    _fail("E_CFG_REFERENCE", f"/local/platforms/{platform}/tools/{tool_id}", "tool is not declared")
                target_tools[tool_id] = _absolute_path(executable, f"/local/platforms/{platform}/tools/{tool_id}", platform=platform)
    return result


@dataclass(frozen=True)
class ResolvedProfile:
    role: str
    profile_id: str
    runtime_id: str
    adapter_id: str
    platform: Optional[str]
    semantic_snapshot: bytes
    semantic_sha256: str
    source_report: Tuple[Mapping[str, Any], ...]


def resolve_profile(config: Mapping[str, Any], registry: AdapterRegistry, *, role: str, profile_id: Optional[str] = None,
                   platform: Optional[str] = None, local: Optional[Mapping[str, Any]] = None,
                   trusted_policy: Optional[Mapping[str, Any]] = None) -> ResolvedProfile:
    """Resolve one explicit role/profile without probing or starting a runtime."""

    if local is not None and not platform:
        _fail("E_CFG_PLATFORM", "/local", "local overrides require an explicit platform")
    effective = apply_local_overrides(config, local, platform=platform) if local is not None else copy.deepcopy(dict(config))
    validated = validate_config(effective, registry)
    if role not in validated["roles"]:
        _fail("E_CFG_REFERENCE", f"/roles/{role}", "role binding does not exist")
    binding = validated["roles"][role]
    if binding.get("mode") == "disabled":
        _fail("E_CFG_CAPABILITY", f"/roles/{role}", "role is disabled")
    if binding.get("mode") == "current_session":
        _fail("E_CFG_CAPABILITY", f"/roles/{role}", "current_session has no profile snapshot")
    selected = profile_id or binding.get("profile")
    if profile_id is not None and profile_id != binding.get("profile"):
        _fail("E_CFG_POLICY", f"/roles/{role}/profile", "explicit profile cannot bypass role binding")
    if selected not in validated["profiles"]:
        _fail("E_CFG_REFERENCE", f"/roles/{role}/profile", "selected profile does not exist")
    profile = validated["profiles"][selected]
    runtime_id = profile["runtime"]
    runtime = validated["runtimes"][runtime_id]
    descriptor = registry.require(runtime["adapter"], f"/runtimes/{runtime_id}/adapter")
    project_policy = _policy(validated.get("policies", {}), "/policies")
    host_policy = _policy(trusted_policy, "/trusted_policy")
    _policy_allows(project_policy, role=role, profile_id=selected, model=profile["model"], descriptor=descriptor, credential_refs=profile.get("credential_refs", []))
    _policy_allows(host_policy, role=role, profile_id=selected, model=profile["model"], descriptor=descriptor, credential_refs=profile.get("credential_refs", []))
    command = runtime.get("command_by_platform", {}).get(platform, runtime["command"]) if platform else runtime["command"]
    semantic = {
        "schema_version": 2,
        "role": role,
        "profile_id": selected,
        "runtime_id": runtime_id,
        "adapter": runtime["adapter"],
        "adapter_descriptor": {"id": descriptor.adapter_id, "version": descriptor.descriptor_version, "capabilities": list(descriptor.capabilities), "provider": descriptor.provider, "deployment": descriptor.deployment, "sha256": descriptor.descriptor_sha256},
        "command": list(command),
        "model": copy.deepcopy(profile["model"]),
        "options": copy.deepcopy(profile.get("options", {})),
        "credential_refs": copy.deepcopy(profile.get("credential_refs", [])),
        "platform": platform,
        "policies": {"project": project_policy, "trusted": host_policy},
    }
    raw = canonical_json_bytes(semantic)
    return ResolvedProfile(role, selected, runtime_id, runtime["adapter"], platform, raw, hashlib.sha256(raw).hexdigest(),
                           ({"source_kind": "project", "path": "/profiles/" + selected},
                            {"source_kind": "project", "path": "/runtimes/" + runtime_id}))


__all__ = ["AdapterDescriptor", "AdapterRegistry", "ConfigError", "ResolvedProfile", "apply_local_overrides",
           "canonical_json_bytes", "load_strict_json", "resolve_profile", "validate_config"]
