#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kit_roles —— 角色绑定与配置中心（3.0 第二轮，docs/themis-tally-3.0-r2-角色绑定与配置中心.md）。

配置 v3 的五个键（runtimes、profiles、roles、presets、active_preset）的解析与校验（D1）、适配器登记表（D2）、
给调度器解析角色绑定的接口（D5），以及运行中切换的判定（D8）。由 kit_config 与 pi_dispatch 惰性导入：配置里没有
这五个键、合同也不是按角色写的时候，两边都不导入本模块（D12）。

给调度器的函数不抛异常，返回（值, 错误），错误是 None 或 {"message", "code"}：调度器以脚本方式运行时模块名是
__main__，这里的 `import pi_dispatch` 载入的是另一份模块，两边的 DispatchError 不是同一个类。只依赖标准库。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import pi_dispatch as pd  # noqa: E402

V3_KEYS = ("runtimes", "profiles", "roles", "presets", "active_preset")
ROLES = ("planning_review", "contract", "execution", "scheduler_agent")
#: 每个角色允许的模式（上位设计 6.3）
ROLE_MODES = {
    "planning_review": ("interactive_host", "headless"),
    "contract": ("manual", "headless"),
    "execution": ("headless",),
    "scheduler_agent": ("disabled", "headless"),
}
#: 没写的角色取的默认值；execution 没写时由合同决定（2.10 的兼容预设，上位设计 11 节）
DEFAULT_ROLES: Dict[str, Optional[Dict[str, Any]]] = {
    "planning_review": {"mode": "interactive_host"},
    "contract": {"mode": "manual"},
    "execution": None,
    "scheduler_agent": {"mode": "disabled"},
}
#: 适配器登记表（D2）：静态表，不是插件。接入一个 CLI 要先实测（上位设计 7.3）。
ADAPTERS: Dict[str, Dict[str, Any]] = {
    "pi": {"program": "pi", "headless_roles": ("execution", "contract"), "host": False, "list_models": True,
           "auth": True, "options": ("thinking",)},
    "claude-code": {"program": "claude", "headless_roles": (), "host": True, "list_models": False, "auth": False,
                    "options": ()},
    "codex": {"program": "codex", "headless_roles": (), "host": True, "list_models": False, "auth": False,
              "options": ()},
    "opencode": {"program": "opencode", "headless_roles": (), "host": False, "list_models": False, "auth": False,
                 "options": ()},
}
HOST_ADAPTERS = tuple(name for name, spec in ADAPTERS.items() if spec["host"])
RUNTIME_KEYS = ("adapter",)
PROFILE_KEYS = ("runtime", "model", "options", "credential_env")
PRESET_KEYS = ("description", "roles")
#: 写进生效绑定元组的字段（D8 的比较、D5 的记录）
BINDING_FIELDS = ("mode", "profile", "runtime", "adapter", "provider", "model", "thinking")


def has_v3_keys(config: Any) -> bool:
    return isinstance(config, dict) and any(key in config for key in V3_KEYS)


# ---------------------------------------------------------------------------
# 校验（D1）
# ---------------------------------------------------------------------------

def _id_ok(value: Any) -> bool:
    return isinstance(value, str) and bool(pd.TASK_ID_RE.match(value))


def _extra_keys(obj: Dict[str, Any], allowed: Tuple[str, ...]) -> List[str]:
    return sorted(str(key) for key in obj if not str(key).startswith("_") and key not in allowed)


def _entries(mapping: Dict[str, Any]) -> List[Tuple[str, Any]]:
    """{ID: 对象} 这一层的条目；下划线开头的是说明键，不是条目（与每个对象里的说明键同一规则）。"""
    return [(str(key), value) for key, value in mapping.items() if not str(key).startswith("_")]


def _shown(value: Any) -> str:
    """错误里要提到的值：只有像 ID、又不像凭据的字符串才原样显示，其余一律隐去（D9：不输出凭据值，闸二第 2 片 B1）。"""
    if isinstance(value, str) and pd.TASK_ID_RE.match(value) and not pd.secret_like_paths({"v": value}):
        return repr(value)
    return "（值不显示）"


def _model_errors(where: str, model: Any) -> List[str]:
    if not isinstance(model, dict):
        return ["%s.model 必须是 {provider, id}" % where]
    errors = ["%s.model 有未知键：%s" % (where, "、".join(_extra_keys(model, ("provider", "id"))))] \
        if _extra_keys(model, ("provider", "id")) else []
    for field in ("provider", "id"):
        value = model.get(field)
        if not isinstance(value, str) or not pd.MODEL_TOKEN_RE.match(value) or pd.PLACEHOLDER_RE.search(value):
            errors.append("%s.model.%s 必须是精确的 ID" % (where, field))
    return errors


def _adapter_of(config: Dict[str, Any], runtime_id: Any) -> Optional[str]:
    runtimes = config.get("runtimes")
    if not isinstance(runtime_id, str) or runtime_id.startswith("_") or not isinstance(runtimes, dict) \
            or not isinstance(runtimes.get(runtime_id), dict):
        return None
    adapter = runtimes[runtime_id].get("adapter")
    return adapter if isinstance(adapter, str) and adapter in ADAPTERS else None


def _check_runtimes(config: Dict[str, Any]) -> List[str]:
    runtimes = config.get("runtimes")
    if not isinstance(runtimes, dict):
        return ["runtimes 必须是对象 {ID: {adapter}}"]
    errors: List[str] = []
    for runtime_id, spec in _entries(runtimes):
        where = "runtimes.%s" % runtime_id
        if not _id_ok(runtime_id):
            errors.append("%s：ID 不合法" % where)
        if not isinstance(spec, dict):
            errors.append("%s 必须是对象" % where)
            continue
        extra = _extra_keys(spec, RUNTIME_KEYS)
        if extra:
            errors.append("%s 只接受 adapter，不能写 %s（命令路径放 .agent/dispatch.local.json）" % (where, "、".join(extra)))
        adapter = spec.get("adapter")
        if not isinstance(adapter, str) or adapter not in ADAPTERS:
            errors.append("%s.adapter 必须是 %s 之一" % (where, "、".join(ADAPTERS)))
    return errors


def _check_profiles(config: Dict[str, Any]) -> List[str]:
    profiles = config.get("profiles")
    if not isinstance(profiles, dict):
        return ["profiles 必须是对象 {ID: {runtime, model, options, credential_env}}"]
    errors: List[str] = []
    for profile_id, spec in _entries(profiles):
        where = "profiles.%s" % profile_id
        if not _id_ok(profile_id):
            errors.append("%s：ID 不合法" % where)
        if not isinstance(spec, dict):
            errors.append("%s 必须是对象" % where)
            continue
        extra = _extra_keys(spec, PROFILE_KEYS)
        if extra:
            errors.append("%s 有未知键：%s" % (where, "、".join(extra)))
        adapter = _adapter_of(config, spec.get("runtime"))
        if adapter is None:
            errors.append("%s.runtime %s 没有登记（或它的 adapter 无效）" % (where, _shown(spec.get("runtime"))))
        errors += _model_errors(where, spec.get("model"))
        options = spec.get("options", {})
        if not isinstance(options, dict):
            errors.append("%s.options 必须是对象" % where)
        elif adapter is not None:
            allowed = ADAPTERS[adapter]["options"]
            extra = _extra_keys(options, allowed)
            if extra:
                errors.append("%s.options 有 %s 不接受的键：%s" % (where, adapter, "、".join(extra)))
            if "thinking" in options and options["thinking"] not in pd.FALLBACK_THINKING_LEVELS:
                errors.append("%s.options.thinking 必须是 %s 之一" % (where, "、".join(pd.FALLBACK_THINKING_LEVELS)))
        names = spec.get("credential_env", [])
        if not isinstance(names, list) or any(not isinstance(name, str) or not pd.ENV_NAME_RE.match(name)
                                              for name in names):
            errors.append("%s.credential_env 必须是环境变量名的数组" % where)
    return errors


def _binding_errors(config: Dict[str, Any], where: str, role: str, binding: Any) -> List[str]:
    if not isinstance(binding, dict):
        return ["%s 必须是对象 {mode, …}" % where]
    mode = binding.get("mode")
    if not isinstance(mode, str) or mode not in ROLE_MODES[role]:
        return ["%s.mode 必须是 %s 之一（当前 %s）" % (where, "、".join(ROLE_MODES[role]), _shown(mode))]
    allowed = {"interactive_host": ("mode", "host"), "headless": ("mode", "profile") + (
        ("cadence_seconds",) if role == "scheduler_agent" else ()), "manual": ("mode",), "disabled": ("mode",)}[mode]
    errors = ["%s 有未知键：%s" % (where, "、".join(_extra_keys(binding, allowed)))] \
        if _extra_keys(binding, allowed) else []
    if mode == "interactive_host" and "host" in binding and (
            not isinstance(binding["host"], str) or binding["host"] not in HOST_ADAPTERS):
        errors.append("%s.host 必须是 %s 之一" % (where, "、".join(HOST_ADAPTERS)))
    if mode == "headless":
        profiles = config.get("profiles") if isinstance(config.get("profiles"), dict) else {}
        profile = binding.get("profile")
        if not isinstance(profile, str) or profile.startswith("_") or profile not in profiles:
            errors.append("%s.profile %s 没有登记" % (where, _shown(profile)))
        if "cadence_seconds" in binding:  # 写了就必须合法，null 也不行（闸二第 2 片 S3）
            cadence = binding["cadence_seconds"]
            if isinstance(cadence, bool) or not isinstance(cadence, int) or cadence < 60:
                errors.append("%s.cadence_seconds 必须是至少 60 的整数" % where)
    return errors


def _check_roles(config: Dict[str, Any]) -> List[str]:
    roles = config.get("roles")
    if not isinstance(roles, dict):
        return ["roles 必须是对象 {角色: {mode, …}}"]
    errors = ["roles 有未知角色：%s（只有 %s）" % ("、".join(_extra_keys(roles, ROLES)), "、".join(ROLES))] \
        if _extra_keys(roles, ROLES) else []
    for role in ROLES:
        if role in roles:
            errors += _binding_errors(config, "roles.%s" % role, role, roles[role])
    return errors


def _check_presets(config: Dict[str, Any]) -> List[str]:
    presets = config.get("presets")
    if not isinstance(presets, dict):
        return ["presets 必须是对象 {名: {description, roles}}"]
    errors: List[str] = []
    for name, spec in _entries(presets):
        where = "presets.%s" % name
        if not _id_ok(name):
            errors.append("%s：名字不合法" % where)
        if not isinstance(spec, dict):
            errors.append("%s 必须是对象" % where)
            continue
        extra = _extra_keys(spec, PRESET_KEYS)
        if extra:
            errors.append("%s 有未知键：%s" % (where, "、".join(extra)))
        if "description" in spec and not isinstance(spec["description"], str):
            errors.append("%s.description 必须是字符串" % where)
        roles = spec.get("roles")
        if not isinstance(roles, dict) or not [role for role in roles if not str(role).startswith("_")]:
            errors.append("%s.roles 至少写一个角色" % where)
            continue
        if _extra_keys(roles, ROLES):
            errors.append("%s.roles 有未知角色：%s" % (where, "、".join(_extra_keys(roles, ROLES))))
        for role in ROLES:
            if role in roles:
                errors += _binding_errors(config, "%s.roles.%s" % (where, role), role, roles[role])
    return errors


def _check_active_preset(config: Dict[str, Any]) -> List[str]:
    name = config.get("active_preset")
    presets = config.get("presets") if isinstance(config.get("presets"), dict) else {}
    if not isinstance(name, str) or name.startswith("_") or name not in presets:
        return ["active_preset %s 不是已有的方案" % _shown(name)]
    return []


CHECKS = {"runtimes": _check_runtimes, "profiles": _check_profiles, "roles": _check_roles,
          "presets": _check_presets, "active_preset": _check_active_preset}


def check_key(config: Dict[str, Any], key: str) -> List[str]:
    """kit_config 的 KEYS 检查：key 缺省时不调用这里。

    先查这个键之下疑似凭据的位置：有就只报这一条（只含键路径），不再报其他会提到取值的错误（闸二第 2 片 B1）。
    """
    suspicious = pd.secret_like_paths({key: config[key]})
    if suspicious:
        return ["%s 里有疑似凭据（%s）：凭据只写环境变量名（credential_env），值用 config secret set 存" % (
            key, "、".join(suspicious[:5]))]
    return CHECKS[key](config)


# ---------------------------------------------------------------------------
# 生效绑定（D5、D8）
# ---------------------------------------------------------------------------

def effective_binding(config: Dict[str, Any], role: str) -> Optional[Dict[str, Any]]:
    """某个角色的生效绑定；execution 没写时是 None（由合同决定）。"""
    roles = config.get("roles") if isinstance(config.get("roles"), dict) else {}
    binding = roles.get(role, DEFAULT_ROLES[role])
    return dict(binding) if isinstance(binding, dict) else None


def binding_tuple(config: Dict[str, Any], role: str) -> Optional[Tuple[Any, ...]]:
    """D8 比较的元组（mode, profile, runtime, adapter, provider, model, thinking）；没有绑定时 None。

    写入前的配置可能是手改坏的：任何字段类型不对都按“没有这一项”处理，这里不抛异常。
    """
    binding = effective_binding(config, role)
    if binding is None:
        return None

    def text(value: Any) -> Optional[str]:
        return value if isinstance(value, str) else None

    profile_id = text(binding.get("profile"))
    profiles = config.get("profiles") if isinstance(config.get("profiles"), dict) else {}
    profile = profiles.get(profile_id) if profile_id is not None and isinstance(profiles.get(profile_id), dict) else {}
    model = profile.get("model") if isinstance(profile.get("model"), dict) else {}
    options = profile.get("options") if isinstance(profile.get("options"), dict) else {}
    runtime = text(profile.get("runtime"))
    return (text(binding.get("mode")), profile_id, runtime, _adapter_of(config, runtime), text(model.get("provider")),
            text(model.get("id")), text(options.get("thinking", pd.DEFAULT_THINKING)) if profile else None)


def resolve_role_executor(config: Dict[str, Any], role: str) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """按角色写的合同第一次建立版本记录时用的执行模型（D4、D5）：返回（值, 错误），不抛异常（D12）。

    值含 role、profile、runtime、adapter、active_preset、provider、model、thinking。错误码：没有绑定、模式不对、
    与 manual 冲突是 EXIT_USAGE；适配器本轮没有接通这个角色是 EXIT_BLOCKED（D6）。
    """
    try:
        if role not in ("execution", "contract"):
            return None, {"message": "executor.role 只能是 execution 或 contract：%s" % _shown(role), "code": pd.EXIT_USAGE}
        binding = effective_binding(config, role)
        if binding is None or binding.get("mode") != "headless":
            if role == "contract" and binding is not None and binding.get("mode") == "manual":
                return None, {"message": "contract 角色是 manual（规划审核端手写合同），合同却写了 role:contract："
                                         "改绑定（config role set contract <profile>）或改合同", "code": pd.EXIT_USAGE}
            return None, {"message": "按角色写的合同需要 %s 角色的 headless 绑定：config role set %s <profile>"
                                     % (role, role), "code": pd.EXIT_USAGE}
        mode, profile_id, runtime, adapter, provider, model, thinking = binding_tuple(config, role)
        if adapter is None or not provider or not model:
            return None, {"message": "%s 角色绑定的 profile %s 无效：先修好配置（config validate）" % (role, _shown(profile_id)),
                          "code": pd.EXIT_USAGE}
        if role not in ADAPTERS[adapter]["headless_roles"]:
            return None, {"message": "%s 角色绑定到 %s（runtime %s）：这个适配器本轮没有接通 %s，不派遣"
                                     % (role, adapter, runtime, role), "code": pd.EXIT_BLOCKED}
        preset = config.get("active_preset") if isinstance(config.get("active_preset"), str) else None
        return {"role": role, "profile": profile_id, "runtime": runtime, "adapter": adapter, "active_preset": preset,
                "provider": provider, "model": model, "thinking": thinking}, None
    except (pd.DispatchError, OSError, ValueError, TypeError) as exc:  # 这份模块的 DispatchError 穿不过边界
        return None, {"message": "解析角色绑定失败：%s" % exc, "code": getattr(exc, "code", pd.EXIT_USAGE)}


def in_flight_attempts(repo: Any) -> Tuple[List[str], List[str]]:
    """正在运行的 attempt（task/attempt-NNN）与扫描中列不出来的位置。判定与 collect --recover 相同
    （pd.attempt_in_flight）；不跟随链接。列不出来的不当作“没有在运行”（闸二第 2 片 S4）。"""
    found: List[str] = []
    problems: List[str] = []
    runs = repo.runs_dir
    try:
        tasks = sorted(entry for entry in runs.iterdir() if entry.is_dir() and not pd.is_link_or_junction(entry)
                       and pd.TASK_ID_RE.match(entry.name)) if runs.is_dir() else []
    except OSError as exc:
        return found, ["%s（%s）" % (runs, exc.strerror or exc)]
    for task in tasks:
        try:
            attempts = sorted(entry for entry in task.iterdir() if pd.ATTEMPT_DIR_RE.match(entry.name)
                              and entry.is_dir() and not pd.is_link_or_junction(entry))
        except OSError as exc:
            problems.append("%s（%s）" % (task, exc.strerror or exc))
            continue
        found += ["%s/%s" % (task.name, attempt.name) for attempt in attempts if pd.attempt_in_flight(attempt)]
    return found, problems


def binding_switch_in_flight(repo: Any, old_config: Dict[str, Any],
                             new_config: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """D8：这次写入改变了 execution 或 contract 的生效绑定时，返回（在运行的 attempt, 扫描时列不出来的位置）；
    绑定没变时两个都是空。"""
    if all(binding_tuple(old_config, role) == binding_tuple(new_config, role) for role in ("execution", "contract")):
        return [], []
    return in_flight_attempts(repo)
