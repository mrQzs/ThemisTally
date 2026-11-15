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

import json
import os
import shutil
import stat
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import pi_dispatch as pd  # noqa: E402

V3_KEYS = pd.V3_CONFIG_KEYS
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
    # r3 第 154 轮：七端的规划端在 claude 上无头运行，档位写在 options.thinking（hub 传给 claude 的 --effort）
    "claude-code": {"program": "claude", "headless_roles": (), "host": True, "list_models": False, "auth": False,
                    "options": ("thinking",)},
    "codex": {"program": "codex", "headless_roles": (), "host": True, "list_models": False, "auth": False,
              "options": ()},
    "opencode": {"program": "opencode", "headless_roles": (), "host": False, "list_models": False, "auth": False,
                 "options": ()},
    # r3 第 154 轮：quizs 只承载七端的岗位（hub_roles），不接四个角色的 headless
    "quizs": {"program": "quizs", "headless_roles": (), "host": False, "list_models": False, "auth": False,
              "options": ("thinking",)},
}
HOST_ADAPTERS = tuple(name for name, spec in ADAPTERS.items() if spec["host"])
RUNTIME_KEYS = ("adapter",)
PROFILE_KEYS = ("runtime", "model", "options", "credential_env")
PRESET_KEYS = ("description", "roles")
#: 写进生效绑定元组的字段（D8 的比较、D5 的记录）
BINDING_FIELDS = ("mode", "profile", "runtime", "adapter", "provider", "model", "thinking")
#: 七端的岗位（模型配置，r3 第 154 轮）：键是岗位，值是这个岗位现在允许的适配器。岗位的工具、时限、工作目录留在 hub 的
#: 名册里（那是安全边界），这里只管“用哪个运行时、哪个模型、什么档位”。名册里的工具名是按载体写的：一个岗位换载体之前
#: 要先有那个载体的工具映射并实测过，所以每个岗位只列已经跑过的载体。r3 第 156 轮：合同端、审核端加 quizs（MiniMax、仓库视图）：工具映射在假提供方上跑过；真实模型的重放（模型配置 M5）跑完之前不绑，绑定照样要站主同意。
HUB_POST_ADAPTERS: Dict[str, Tuple[str, ...]] = {
    "coordinator": ("quizs", "pi"),
    "planner": ("claude-code",),
    "contract": ("pi", "quizs"),
    "gate": ("pi",),
    "audit": ("pi", "quizs"),
    "exec": ("pi",),
}
HUB_POSTS = tuple(HUB_POST_ADAPTERS)
HUB_BINDING_KEYS = ("profile", "fallback")
#: 预览里岗位一侧的字段（模型配置 §3.4，r3 第 162 轮）：与 config hub show 一行里的同名字段相同，另加 source 与替补
HUB_SIDE_FIELDS = ("profile", "runtime", "adapter", "provider", "model", "thinking")
#: 各岗位没配时 hub 用的缺省（与 kit_hub.ROSTER 的同名字段逐项相同，tests/test_kit_hub.py 有一条核对）：config hub show
#: 要在没装 kit_hub.py 的仓库里也能显示，所以这里另放一份
HUB_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "coordinator": {"adapter": "quizs", "provider": "deepseek", "model": "deepseek-flash", "thinking": "high",
                    "fallback": {"adapter": "pi", "provider": "dsf", "model": "deepseek-flash", "thinking": "high"}},
    "planner": {"adapter": "claude-code", "provider": None, "model": "claude-opus-5-5", "thinking": "max", "fallback": None},
    "contract": {"adapter": "pi", "provider": "minimax", "model": "MiniMax-M3.1-Flash", "thinking": "high", "fallback": None},
    "gate": {"adapter": "pi", "provider": "cc-switch-zhipu-glm", "model": "glm-5.3", "thinking": "high", "fallback": None},
    "audit": {"adapter": "pi", "provider": "minimax", "model": "MiniMax-M3.1-Flash", "thinking": "max", "fallback": None},
    "exec": {"adapter": "pi", "provider": "cc-switch-step-fun", "model": "step-5-preview", "thinking": "high", "fallback": None},
}
#: 岗位在 hub 名册里的工人与中文名（工人名与 kit_hub.ROSTER 里这个 role 的工人相同，tests/test_kit_hub.py 有一条核对）：
#: 改岗位绑定时查这个岗位此刻有没有回合在跑（模型配置 §3.3，r3 第 163 轮）。执行端不列：执行模型在合同写出时就定下了，
#: 改岗位影响不到在途的合同（§3.3 的执行端例外）
HUB_POST_AGENTS: Dict[str, Tuple[str, str]] = {
    "coordinator": ("womovie-c8", "协调人"),
    "planner": ("planner-opus", "规划端"),
    "contract": ("contract-glm", "合同端"),
    "gate": ("gate-sonnet", "门禁端"),
    "audit": ("audit-sonnet", "审核端"),
}
#: 岗位一回合拿到的时限（秒）与工具面（模型配置 §6 第二条，r3 第 168 轮）：抄 hub 名册（kit_hub.ROSTER）的 timeout 与 tools，名册的
#: allowed_rules 换掉同名的工具（规划端的 Bash 只许 npm view）。与 HUB_DEFAULTS 一样另放一份，tests/test_kit_hub.py 有一条核对。
#: 执行端的时限与工具由合同与调度器定，不列
HUB_TURN_LIMITS: Dict[str, Tuple[int, Tuple[str, ...]]] = {
    "coordinator": (600, ("read", "grep", "find", "ls")),
    "planner": (2400, ("Read", "Grep", "Glob", "Bash(npm view:*)")),
    "contract": (2400, ("read", "grep", "find", "ls")),
    "gate": (2400, ("read", "grep", "find", "ls", "edit", "write", "bash")),
    "audit": (2400, ("read", "grep", "find", "ls")),
}
#: 绑在 quizs 上的岗位每回合的预算（抄 kit_hub 的 QUIZS_TURN_BUDGETS、QUIZS_VIEW_BUDGETS 与 QUIZS_REPO_VIEW_ROLES，同一条测试核对）：
#: 读整棵仓库的合同端、审核端用大的一份
QUIZS_TURN_BUDGETS: Dict[str, int] = {"max_requests": 32, "max_tool_calls": 48, "max_input_bytes": 2097152,
                                      "max_response_bytes": 8388608, "max_object_bytes": 8388608}
QUIZS_VIEW_BUDGETS: Dict[str, int] = dict(QUIZS_TURN_BUDGETS, max_requests=128, max_tool_calls=128)
QUIZS_VIEW_POSTS = ("contract", "audit")
#: claude 的 --effort 取值（claude --help，2026-11-12 核对）
CLAUDE_EFFORTS = ("low", "medium", "high", "xhigh", "max")


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
            levels = CLAUDE_EFFORTS if adapter == "claude-code" else pd.FALLBACK_THINKING_LEVELS
            if "thinking" in options and options["thinking"] not in levels:
                errors.append("%s.options.thinking 必须是 %s 之一" % (where, "、".join(levels)))
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


def _check_hub_roles(config: Dict[str, Any]) -> List[str]:
    """七端的岗位绑定：{岗位: {profile, fallback}}。fallback 只用于 quizs 上的岗位（证书过期等起不了时这一回合退回它），
    替补自己不能再是 quizs。"""
    hub_roles = config.get("hub_roles")
    if not isinstance(hub_roles, dict):
        return ["hub_roles 必须是对象 {岗位: {profile, fallback}}"]
    extra = _extra_keys(hub_roles, HUB_POSTS)
    errors = ["hub_roles 有未知岗位：%s（只有 %s）" % ("、".join(extra), "、".join(HUB_POSTS))] if extra else []
    profiles = config.get("profiles") if isinstance(config.get("profiles"), dict) else {}
    for post in HUB_POSTS:
        if post not in hub_roles:
            continue
        where, binding = "hub_roles.%s" % post, hub_roles[post]
        if not isinstance(binding, dict):
            errors.append("%s 必须是对象 {profile, fallback}" % where)
            continue
        if _extra_keys(binding, HUB_BINDING_KEYS):
            errors.append("%s 有未知键：%s" % (where, "、".join(_extra_keys(binding, HUB_BINDING_KEYS))))
        adapters: Dict[str, Optional[str]] = {}
        for field in HUB_BINDING_KEYS:
            if field == "fallback" and field not in binding:
                continue
            profile = binding.get(field)
            if not isinstance(profile, str) or profile.startswith("_") or not isinstance(profiles.get(profile), dict):
                errors.append("%s.%s %s 没有登记" % (where, field, _shown(profile)))
                continue
            adapters[field] = _adapter_of(config, profiles[profile].get("runtime"))
            if adapters[field] is not None and adapters[field] not in HUB_POST_ADAPTERS[post]:
                errors.append("%s.%s 的适配器 %s 不能用在 %s 岗位（允许：%s）"
                              % (where, field, adapters[field], post, "、".join(HUB_POST_ADAPTERS[post])))
        if "fallback" in adapters and (adapters.get("profile") != "quizs" or adapters["fallback"] == "quizs"):
            errors.append("%s.fallback 只用于 quizs 上的岗位，替补自己不能是 quizs" % where)
    return errors


CHECKS = {"runtimes": _check_runtimes, "profiles": _check_profiles, "roles": _check_roles,
          "presets": _check_presets, "active_preset": _check_active_preset, "hub_roles": _check_hub_roles}


def check_key(config: Dict[str, Any], key: str) -> List[str]:
    """kit_config 的 KEYS 检查：key 缺省时不调用这里。

    先查这个键之下疑似凭据的位置：有就只报这一条（只含键路径），不再报其他会提到取值的错误（闸二第 2 片 B1）。
    """
    secret = pd.secret_config_error(config, key)
    if secret is not None:  # kit_config.validate_config 已经先查过；这里再挡一次，直接调用时同样不回显取值
        return [secret]
    return CHECKS[key](config)


def config_errors(config: Dict[str, Any]) -> List[str]:
    """配置里出现的 v3 键逐个校验（check_key，先过共用的凭据检查）的错误；都合法或都没写时为空。

    调度器解析绑定、比较写死合同之前先过这里（D9）：取值不合法或含疑似凭据时不进版本记录与提示。
    """
    errors: List[str] = []
    for key in V3_KEYS:
        if key in config:
            errors.extend(check_key(config, key))
    return errors


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


def hub_binding(config: Dict[str, Any], post: str) -> Optional[Dict[str, Any]]:
    """七端某个岗位在配置里的绑定，解析成 hub 要的字段（profile、runtime、adapter、provider、model、thinking、fallback）；
    没写这个岗位时 None（hub 用内核里的缺省）。调用之前先整份校验；字段类型不对照“没有这一项”处理，这里不抛异常。"""
    hub_roles = config.get("hub_roles") if isinstance(config.get("hub_roles"), dict) else {}
    binding = hub_roles.get(post)
    if not isinstance(binding, dict):
        return None
    profiles = config.get("profiles") if isinstance(config.get("profiles"), dict) else {}

    def resolved(profile_id: Any) -> Optional[Dict[str, Any]]:
        profile = profiles.get(profile_id) if isinstance(profile_id, str) else None
        if not isinstance(profile, dict):
            return None
        model = profile.get("model") if isinstance(profile.get("model"), dict) else {}
        options = profile.get("options") if isinstance(profile.get("options"), dict) else {}
        runtime = profile.get("runtime") if isinstance(profile.get("runtime"), str) else None
        return {"profile": profile_id, "runtime": runtime, "adapter": _adapter_of(config, runtime),
                "provider": model.get("provider"), "model": model.get("id"),
                "thinking": options.get("thinking", pd.DEFAULT_THINKING)}

    primary = resolved(binding.get("profile"))
    if primary is None:
        return None
    primary["fallback"] = resolved(binding.get("fallback")) if "fallback" in binding else None
    return primary


def hub_side(config: Dict[str, Any], post: str) -> Dict[str, Any]:
    """预览里一个岗位生效绑定的一侧：source（config 或 default）、六个字段与替补（同样六个字段；没有替补时 None）。
    没配这个岗位时取内核缺省，与 config hub show 的一行一致。"""
    binding = hub_binding(config, post)
    spec = dict(HUB_DEFAULTS[post], profile=None, runtime=None) if binding is None else binding
    fallback = spec.get("fallback")
    side: Dict[str, Any] = {"source": "default" if binding is None else "config"}
    side.update((field, spec.get(field)) for field in HUB_SIDE_FIELDS)
    side["fallback"] = {field: fallback.get(field) for field in HUB_SIDE_FIELDS} if isinstance(fallback, dict) else None
    return side


def hub_changes(old_config: Dict[str, Any], new_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """这次写入改变了哪些岗位的生效绑定（模型配置 §3.4）：前后不同的岗位各一项 {post, before, after}。不只 hub set、
    hub unset：改了岗位绑着的 profile，那个岗位也在这里。"""
    changes = []
    for post in HUB_POSTS:
        before, after = hub_side(old_config, post), hub_side(new_config, post)
        if before != after:
            changes.append({"post": post, "before": before, "after": after})
    return changes


def resolve_role_executor(config: Dict[str, Any], role: str) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """按角色写的合同第一次建立版本记录时用的执行模型（D4、D5）：返回（值, 错误），不抛异常（D12）。

    值含 role、profile、runtime、adapter、active_preset、provider、model、thinking。错误码：没有绑定、模式不对、
    与 manual 冲突是 EXIT_USAGE；适配器本轮没有接通这个角色是 EXIT_BLOCKED（D6）。
    """
    try:
        if role not in ("execution", "contract"):
            return None, {"message": "executor.role 只能是 execution 或 contract：%s" % _shown(role), "code": pd.EXIT_USAGE}
        errors = config_errors(config)
        if errors:  # 先整份校验 v3 键（D9）：错误只含位置与像 ID 的值
            return None, {"message": "角色绑定的配置无效：%s；先修好配置（config validate）" % "；".join(errors[:3]),
                          "code": pd.EXIT_USAGE}
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
    （pd.state_in_flight）；task 与 attempt 目录不跟随链接。列不出来的不当作“没有在运行”（闸二第 2 片 S4）：
    每一处都用 _lstat 探测，只有“不存在”才算没有（闸二第 2 片第 3 轮之后）。"""
    found: List[str] = []
    problems: List[str] = []
    runs = repo.runs_dir
    try:
        if _lstat(runs) is None:
            return found, problems
        tasks = sorted(entry for entry in runs.iterdir() if pd.TASK_ID_RE.match(entry.name))
    except OSError as exc:
        return found, [_unreadable(runs, exc)]
    for task in tasks:
        try:
            if not _plain_dir(task):
                continue
            attempts = sorted(entry for entry in task.iterdir() if pd.ATTEMPT_DIR_RE.match(entry.name))
        except OSError as exc:
            problems.append(_unreadable(task, exc))
            continue
        for attempt in attempts:
            try:
                plain = _plain_dir(attempt)
            except OSError as exc:
                problems.append(_unreadable(attempt, exc))
                continue
            if not plain:
                continue
            running, unreadable = _attempt_status(attempt)
            if unreadable is not None:  # 状态读不出来：不能当作“没有在运行”（闸二第 2 片第 2 轮 S4）
                problems.append(unreadable)
            elif running:
                found.append("%s/%s" % (task.name, attempt.name))
    return found, problems


def _lstat(path: Path) -> Optional[os.stat_result]:
    """不跟随链接的 stat；不存在（FileNotFoundError、NotADirectoryError）时 None，其余 OSError 原样抛出。

    os.path.lexists 与新版的 Path.is_dir 会把“看不了”（例如拒绝访问）当成“不存在”；运行中切换的扫描要把它们
    记为列不出来，所以这里自己探测（闸二第 2 片第 3 轮之后）。
    """
    try:
        return os.lstat(str(path))
    except (FileNotFoundError, NotADirectoryError):
        return None


def _plain_dir(path: Path) -> bool:
    """是目录、而且不是链接或 junction；不存在时 False，看不了时抛 OSError。"""
    status = _lstat(path)
    return status is not None and stat.S_ISDIR(status.st_mode) and not pd.is_link_or_junction(path)


def _unreadable(path: Path, exc: OSError) -> str:
    return "%s（%s）" % (path, exc.strerror or type(exc).__name__)


def _attempt_status(run_dir: Path) -> Tuple[bool, Optional[str]]:
    """（是否在运行, 读不出来的说明）。state.json 只读一次，可读性与是否在运行都按这一次读到的对象判断
    （闸二第 2 片第 3 轮 S4）；不存在（还没准备完）时不算在运行，存在却看不了、读不出或不是对象时给出说明。
    已领取的 PREPARED 才看 claim/，同样用 _lstat：看不了就判断不了。"""
    path = run_dir / "state.json"
    try:
        if _lstat(path) is None:
            return False, None
        data = json.loads(path.read_bytes().decode("utf-8"))
    except (OSError, ValueError) as exc:
        return False, "%s（%s）" % (path, getattr(exc, "strerror", None) or type(exc).__name__)
    if not isinstance(data, dict):
        return False, "%s（不是对象）" % path
    state = str(data.get("state", "UNKNOWN"))
    if state != "PREPARED":
        return pd.state_in_flight(state, False), None
    claim = run_dir / "claim"
    try:
        status = _lstat(claim)
    except OSError as exc:
        return False, _unreadable(claim, exc)
    return pd.state_in_flight(state, status is not None and stat.S_ISDIR(status.st_mode)), None


def binding_switch_in_flight(repo: Any, old_config: Dict[str, Any],
                             new_config: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """D8：这次写入改变了 execution 或 contract 的生效绑定时，返回（在运行的 attempt, 扫描时列不出来的位置）；
    绑定没变时两个都是空。"""
    if all(binding_tuple(old_config, role) == binding_tuple(new_config, role) for role in ("execution", "contract")):
        return [], []
    return in_flight_attempts(repo)


def hub_running_turns(repo: Any, posts: List[str]) -> Tuple[List[str], List[str]]:
    """改到的这些岗位此刻在跑的回合（模型配置 §3.3，r3 第 163 轮）：返回（每个有回合在跑的岗位一句, 列不出来的位置）。
    信箱的回合目录 .agent/mailbox/turns/<工人>/<回合>/ 开始时写 inputs.json、结束时写 result.json，没有 result.json 的
    就是在跑（2026-11-14 量过 1054 个回合目录：中途死掉的回合不留下空目录）。没有信箱的仓库没有这个目录，也就没有在跑的；
    执行端不在 HUB_POST_AGENTS 里，不算。列不出来的照 D8 不当作“没有”。"""
    found: List[str] = []
    problems: List[str] = []
    for post in posts:
        if post not in HUB_POST_AGENTS:
            continue
        agent, label = HUB_POST_AGENTS[post]
        where = repo.agent_dir / "mailbox" / "turns" / agent
        try:
            if not _plain_dir(where):
                continue
            turns = sorted(where.iterdir())
        except OSError as exc:
            problems.append(_unreadable(where, exc))
            continue
        running = 0
        for turn in turns:
            try:
                if _plain_dir(turn) and _lstat(turn / "result.json") is None:
                    running += 1
            except OSError as exc:
                problems.append(_unreadable(turn, exc))
        if running:
            found.append("%s（%s）：%d 个回合在跑" % (label, post, running))
    return found, problems


# ---------------------------------------------------------------------------
# 本机文件（D3）
# ---------------------------------------------------------------------------

LOCAL_NAME = "dispatch.local.json"
LOCAL_REL = ".agent/" + LOCAL_NAME
LOCAL_SHAPE = '只接受 {"runtimes": {"<id>": {"command": ["<程序>", "<参数>", …]}}}'


def check_local(repo: Any) -> List[str]:
    """本机文件能不能用（D3）：从仓库根到它的每一级都不是链接、不被 Git 跟踪、已被忽略。返回问题，空表示可用。

    把本机文件强行提交进仓库也不会让它生效（闸一第 1 轮 B1）。经过链接时不再对它运行 git。
    """
    try:
        link = pd.first_link_component(repo.root, LOCAL_REL)
        if link is not None:
            return ["%s 经过链接或 junction（%s），不使用" % (LOCAL_REL, link)]
        problems: List[str] = []
        if pd.git(["ls-files", "--error-unmatch", "--", LOCAL_REL], repo.root, check=False).returncode == 0:
            problems.append("%s 被 Git 跟踪，不使用：本机文件不进提交（git rm --cached %s）" % (LOCAL_REL, LOCAL_REL))
        if pd.git(["check-ignore", "-q", "--", LOCAL_REL], repo.root, check=False).returncode != 0:
            problems.append("%s 没有被 .gitignore 忽略，不使用：运行 kit_install update 补上 kit 的忽略规则" % LOCAL_REL)
        return problems
    except (pd.DispatchError, OSError, ValueError) as exc:  # 这份模块的 DispatchError 穿不过边界（D12）
        return ["%s 无法核对（%s），不使用" % (LOCAL_REL, exc)]


def read_local(repo: Any, config: Dict[str, Any]) -> Tuple[Optional[Dict[str, List[str]]], List[str], List[str]]:
    """读本机文件：（{runtime ID: 命令}, 错误, 警告）。不存在时（{}, [], []）；有错误时命令表为 None，整份不使用（D3）。

    疑似凭据同样是错误，只报位置（D9）；提交的配置里没有登记的 runtime ID 是警告。只读，不运行任何命令。
    """
    path = repo.agent_dir / LOCAL_NAME
    try:
        if _lstat(path) is None:
            return {}, [], []
    except OSError as exc:  # 看不了不当作“没有本机文件”（闸二第 3 片 S3）
        return None, ["%s 看不了（%s），不使用" % (LOCAL_REL, exc.strerror or type(exc).__name__)], []
    errors = check_local(repo)
    if errors:
        return None, errors, []
    try:
        data = json.loads(path.read_bytes().decode("utf-8"))
    except (OSError, ValueError, RecursionError) as exc:
        return None, ["%s 读不出来（%s），不使用" % (LOCAL_REL, type(exc).__name__)], []
    errors = _local_errors(data)
    if errors:
        return None, errors, []
    commands = {runtime_id: list(spec["command"]) for runtime_id, spec in _entries(data.get("runtimes", {}))}
    registered = config.get("runtimes") if isinstance(config.get("runtimes"), dict) else {}
    warnings = ["%s 的 runtime %s 没有在配置的 runtimes 里登记" % (LOCAL_REL, _shown(runtime_id))
                for runtime_id in commands if runtime_id not in registered]
    return commands, [], warnings


def _local_errors(data: Any) -> List[str]:
    """本机文件内容的问题：疑似凭据（D9，只报位置）与形状（D3）；空表示可用。读与写（runtime add --command）共用。"""
    secret = pd.secret_like_paths(data)
    if secret:
        return ["%s 里有疑似凭据（%s），不使用" % (LOCAL_REL, "、".join(secret[:5]))]
    if not isinstance(data, dict) or _extra_keys(data, ("runtimes",)) or not isinstance(data.get("runtimes", {}), dict):
        return ["%s %s，不使用" % (LOCAL_REL, LOCAL_SHAPE)]
    errors: List[str] = []
    for runtime_id, spec in _entries(data.get("runtimes", {})):
        command = spec.get("command") if isinstance(spec, dict) else None
        if not _id_ok(runtime_id) or not isinstance(spec, dict) or _extra_keys(spec, ("command",)) \
                or not isinstance(command, list) or not command or not all(isinstance(part, str) and part for part in command):
            errors.append("%s 的 runtimes.%s 不合法（%s）" % (LOCAL_REL, _shown(runtime_id), LOCAL_SHAPE))
    return errors


def local_command(repo: Any, config: Dict[str, Any], runtime: str) -> Tuple[Optional[List[str]], List[str]]:
    """runtime 在本机文件里的命令与要打印的提示行（“ERROR …”“WARN …”）。没有这一项、或本机文件不可用时命令为 None，
    调用方接着按 PATH 找（D3 的解析顺序）。"""
    commands, errors, warnings = read_local(repo, config)
    lines = ["ERROR %s" % message for message in errors] + ["WARN  %s" % message for message in warnings]
    return (commands or {}).get(runtime), lines


# ---------------------------------------------------------------------------
# 配置中心的命令（设计 4.1；D3、D8、D10）。kit_config 的解析器登记这些子命令，惰性转交到这里（D12）。
# 写入都经过 kit_config.config_transaction：配置锁、整份校验、运行中切换的确认、历史与审计（D7、D8）。
# 显示取值之前先过共用的凭据检查（D9）；探测只运行 --version、--help、--list-models 与 auth check，不调用模型。
# ---------------------------------------------------------------------------

EXIT_OK, EXIT_FAIL, EXIT_USAGE = 0, 1, 2
MODE_WORDS = ("manual", "disabled", "interactive_host")


def _kc() -> Any:
    import kit_config  # noqa: PLC0415  # 由 kit_config 转交过来，这时它已经载入
    return kit_config


def _error(message: str, code: int = EXIT_FAIL) -> Exception:
    return _kc().ConfigError(message, code)


def _run(handler: Any, args: Any) -> int:
    """调度器的错误（找不到 pi、批处理参数不安全等）转成配置中心的错误：一行 ERROR，不冒堆栈。"""
    try:
        return int(handler(args))
    except pd.DispatchError as exc:
        raise _error(str(exc), exc.code if exc.code in (EXIT_FAIL, EXIT_USAGE) else EXIT_FAIL)


def _open(args: Any) -> Tuple[Any, Any, Dict[str, Any]]:
    """读命令（含会运行只读探测的命令）的开头：整份校验配置（validate_config，含共用的凭据检查，D9）。不合法就只报错误、
    退出 1，不显示取值、不运行任何 CLI：坏形状不会冒堆栈，配置里的取值也到不了命令参数里（闸二第 4 片 B1、S3）。"""
    kc = _kc()
    repo = kc._repo(args.repo)
    config = kc.load_config(repo)
    errors = kc.validate_config(config, repo)
    if errors:
        raise _error("配置无效，先修好（config validate）：%s" % "；".join(errors[:5]))
    return kc, repo, config


def _mapping(config: Dict[str, Any], key: str) -> Dict[str, Any]:
    value = config.get(key)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise _error("%s 不是对象：先修好配置（config validate）" % key)
    return value


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _shown_command(command: Optional[List[str]]) -> Optional[List[str]]:
    return [pd.redact_secrets(part) for part in command] if command else None


def cwd_relative_parts(command: List[str]) -> List[str]:
    """命令里不是绝对路径、却在当前目录下存在的部分。run 在 attempt 的 worktree 里运行命令，配置中心的探测在当前目录
    运行：这样的部分两边可能指向不同的文件，探测的结果代表不了 run（闸二总复核第 3 轮 S1）。

    第一项不带路径分隔符时是程序名，按 PATH 找，不算（第 4 轮 S2）。只查得出直接写在命令里的路径：`python -m <模块>`
    这类依赖当前目录的启动方式查不出，没有报出不等于与 run 等价（第 4 轮 S1，知情接受）。
    """
    return [part for index, part in enumerate(command)
            if not os.path.isabs(part) and os.path.exists(part) and (index > 0 or os.path.dirname(part))]


def runtime_command(repo: Any, config: Dict[str, Any], runtime_id: str,
                    adapter: Optional[str] = None) -> Tuple[Optional[List[str]], str, List[str]]:
    """runtime 的命令、来源与提示行，按 D3 的解析顺序：PI_DISPATCH_PI_CMD（只对 pi 适配器）→ 本机文件 → PATH。

    来源是 env、local、path 或 missing。只读，不运行命令。调度器对按角色写的合同用 resolve_pi_command 解析 pi，
    顺序与这里相同（M2 的测试两边一起核对）。adapter 给出时按它解析、不要求 runtime 仍在配置里登记：版本记录里的
    runtime 在 run 时也是这样解析的（config doctor --record，闸二总复核第 2 轮 S4）。
    """
    adapter = adapter if adapter in ADAPTERS else _adapter_of(config, runtime_id)
    if adapter is None:
        return None, "missing", ["ERROR runtime %s 没有登记（或它的 adapter 无效）" % _shown(runtime_id)]
    lines: List[str] = []
    try:
        if adapter == "pi" and os.environ.get("PI_DISPATCH_PI_CMD"):
            return pd.resolve_pi_command(), "env", lines
        command, lines = local_command(repo, config, runtime_id)
        if command is not None:
            return command, "local", lines
        if adapter == "pi":
            return pd.resolve_pi_command(), "path", lines
    except pd.DispatchError as exc:  # PI_DISPATCH_PI_CMD 写错、PATH 上没有 pi
        return None, "missing", lines + ["ERROR %s" % exc]
    found = shutil.which(ADAPTERS[adapter]["program"])  # D3 的既有残余：与 doctor 的查找相同
    return ([found] if found else None), ("path" if found else "missing"), lines


def _probe_version(command: List[str], env: Dict[str, str]) -> Tuple[int, str]:
    pd.ensure_argv_safe(command)  # 本机文件给出的批处理包装：参数含特殊字符时不运行（D3）
    code, out, err = pd.run_capture(list(command) + ["--version"], env=env, timeout=30)
    first = pd.redact_secrets((out or err).strip()).splitlines()  # CLI 的输出照 doctor 脱敏（闸二第 4 片 B2）
    return code, first[0] if first else ""


def _probe_help(command: List[str], env: Dict[str, str]) -> Dict[str, Any]:
    code, out, err = pd.run_capture(list(command) + pd.RESOURCE_FLAGS + ["--help"], env=env, timeout=90)
    info = pd.parse_help(out + err)
    return {"exit_code": code, "thinking_levels": info["thinking_levels"],
            "missing_flags": [flag for flag in pd.REQUIRED_PI_FLAGS + ["--no-context-files"] if flag not in info["flags"]]}


# --- runtime ---------------------------------------------------------------

def cmd_runtime(args: Any) -> int:
    return _run({"list": _runtime_list, "scan": _runtime_scan, "add": _runtime_add, "remove": _runtime_remove,
                 "probe": _runtime_probe}[args.runtime_action], args)


def _runtime_list(args: Any) -> int:
    _kc_, repo, config = _open(args)
    rows = []
    for runtime_id, spec in _entries(_mapping(config, "runtimes")):
        command, source, lines = runtime_command(repo, config, runtime_id)
        rows.append({"id": runtime_id, "adapter": spec.get("adapter") if isinstance(spec, dict) else None,
                     "source": source, "command": _shown_command(command), "notes": lines})
    if args.json:
        _print_json({"runtimes": rows})
        return EXIT_OK
    if not rows:
        print("还没有登记 runtime：config runtime scan --add，或 config runtime add <id> --adapter <适配器>")
    for row in rows:
        print("%-16s %-12s %-8s %s" % (row["id"], row["adapter"], row["source"],
                                       " ".join(row["command"]) if row["command"] else "（找不到命令）"))
        for line in row["notes"]:
            print("  %s" % line)
    return EXIT_OK


def _runtime_scan(args: Any) -> int:
    kc, repo, config = _open(args)
    env, _removed = pd.child_env(config)
    found: List[Dict[str, Any]] = []
    for adapter, spec in ADAPTERS.items():
        path = shutil.which(spec["program"])  # D3 的既有残余：与 doctor 的查找相同
        row: Dict[str, Any] = {"adapter": adapter, "program": spec["program"], "path": path, "version": None,
                               "exit_code": None}
        if path:
            row["exit_code"], row["version"] = _probe_version([path], env)  # 只运行 --version（M1）
        found.append(row)
    added: List[str] = []
    if args.add:
        with kc.config_transaction(repo, "runtime.scan", None, confirm=args.yes) as txn:
            current = txn.config
            runtimes = dict(_mapping(current, "runtimes"))
            for row in found:
                if row["path"] and row["adapter"] not in runtimes:
                    runtimes[row["adapter"]] = {"adapter": row["adapter"]}
                    added.append(row["adapter"])
            if added:
                current["runtimes"] = runtimes
                txn.publish(current)
    if args.json:
        _print_json({"found": found, "added": added})
        return EXIT_OK
    for row in found:
        print("%-10s %s" % (row["program"], "%s（%s）" % (row["path"], row["version"] or "版本未知")
                            if row["path"] else "PATH 上没有"))
    if args.add:
        print("已登记：%s" % ("、".join(added) if added else "没有新的"))
    return EXIT_OK


def _parse_command(text: str) -> List[str]:
    try:
        value = json.loads(text)
    except ValueError:
        value = None
    if not isinstance(value, list) or not value or not all(isinstance(part, str) and part for part in value):
        raise _error('--command 必须是非空的 JSON 字符串数组，例如 ["/usr/local/bin/pi"]', EXIT_USAGE)
    if pd.secret_like_paths(value):
        raise _error("--command 里有疑似凭据：命令里不写凭据，凭据用 config secret set 存", EXIT_USAGE)
    return value


def _write_local(repo: Any, transaction: Any, runtime_id: str, command: Optional[List[str]]) -> bool:
    """写（command 为 None 时删）本机文件里 runtime 的命令（D3、M2）：写之前做同样的三项检查，形状与凭据前后各查一次；
    经写入事务（resource local，历史只存哈希）。transaction 由调用方在持有配置锁时给出：与配置那一步在同一把锁里，
    中间不放锁，别的写入插不进来（闸二第 4 片 S1）。返回是否有变化。"""
    problems = check_local(repo)
    if problems:
        raise _error("；".join(problems))
    txn = transaction("local")
    data = txn.config
    errors = _local_errors(data) if data else []
    if errors:
        raise _error("；".join(errors) + "：先修好本机文件")
    runtimes = dict(data.get("runtimes", {}))
    if command is None:
        if runtime_id not in runtimes:
            return False
        del runtimes[runtime_id]
    else:
        runtimes[runtime_id] = {"command": list(command)}
    data = dict(data, runtimes=runtimes)
    errors = _local_errors(data)
    if errors:
        raise _error("；".join(errors))
    return bool(txn.publish(data))


def _runtime_add(args: Any) -> int:
    kc = _kc()
    repo = kc._repo(args.repo)
    if not _id_ok(args.runtime_id):
        raise _error("runtime ID 不合法（小写字母、数字与连字符）：%s" % _shown(args.runtime_id), EXIT_USAGE)
    if args.adapter not in ADAPTERS:
        raise _error("--adapter 必须是 %s 之一" % "、".join(ADAPTERS), EXIT_USAGE)
    command = _parse_command(args.command) if args.command is not None else None
    with kc.config_transactions(repo, "runtime.add", args.runtime_id, confirm=args.yes,
                                resources=("config", "local") if command is not None else ("config",)) as transaction:
        txn = transaction("config")
        config = txn.config
        runtimes = dict(_mapping(config, "runtimes"))
        current = runtimes.get(args.runtime_id)
        if isinstance(current, dict) and current.get("adapter") != args.adapter and not args.force:
            raise _error("runtime %s 已登记为 %s；改 adapter 要加 --force" % (args.runtime_id, _shown(current.get("adapter"))))
        notes = {key: value for key, value in current.items() if str(key).startswith("_")} \
            if isinstance(current, dict) else {}
        runtimes[args.runtime_id] = dict(notes, adapter=args.adapter)
        config["runtimes"] = runtimes
        changed = txn.publish(config)
        print("%s runtime %s（adapter %s）" % ("已登记" if changed else "没有变化：", args.runtime_id, args.adapter))
        if command is not None:
            _write_local(repo, transaction, args.runtime_id, command)
            print("命令写进了 %s（本机文件，不进提交）" % LOCAL_REL)
    return EXIT_OK


def _runtime_remove(args: Any) -> int:
    kc = _kc()
    repo = kc._repo(args.repo)
    with kc.config_transactions(repo, "runtime.remove", args.runtime_id, confirm=args.yes) as transaction:
        txn = transaction("config")
        config = txn.config
        runtimes = dict(_mapping(config, "runtimes"))
        if args.runtime_id not in runtimes or str(args.runtime_id).startswith("_"):
            raise _error("没有登记 runtime %s" % _shown(args.runtime_id))
        users = [profile_id for profile_id, spec in _entries(_mapping(config, "profiles"))
                 if isinstance(spec, dict) and spec.get("runtime") == args.runtime_id]
        if users:
            raise _error("runtime %s 被 profile %s 引用：先改或删这些 profile" % (args.runtime_id, "、".join(users)))
        del runtimes[args.runtime_id]
        if runtimes:
            config["runtimes"] = runtimes
        else:
            config.pop("runtimes", None)
        txn.publish(config)
        print("已删除 runtime %s" % args.runtime_id)
        try:
            exists = _lstat(repo.agent_dir / LOCAL_NAME) is not None
        except OSError as exc:
            raise _error("%s 看不了（%s）：其中 %s 的命令没有删" % (LOCAL_REL, exc.strerror or type(exc).__name__,
                                                                 args.runtime_id))
        if exists:
            commands, errors, _warnings = read_local(repo, config)
            if errors:
                raise _error("；".join(errors) + "：其中 %s 的命令没有删" % args.runtime_id)
            if commands and args.runtime_id in commands and _write_local(repo, transaction, args.runtime_id, None):
                print("也删去了 %s 里的命令" % LOCAL_REL)
    return EXIT_OK


def _runtime_probe(args: Any) -> int:
    _kc_, repo, config = _open(args)
    adapter = _adapter_of(config, args.runtime_id)
    if adapter is None:
        raise _error("没有登记 runtime %s（或它的 adapter 无效）" % _shown(args.runtime_id))
    command, source, lines = runtime_command(repo, config, args.runtime_id)
    for line in lines:
        print(line, file=sys.stderr)
    if command is None:
        raise _error("找不到 runtime %s 的命令" % args.runtime_id)
    env, _removed = pd.child_env(config)
    code, version = _probe_version(command, env)
    result: Dict[str, Any] = {"runtime": args.runtime_id, "adapter": adapter, "source": source,
                              "command": _shown_command(command), "version_exit_code": code, "version": version}
    if adapter == "pi":  # pi 另加 --help，报缺少的参数（M3）
        result["help"] = _probe_help(command, env)
    ok = code == 0 and (adapter != "pi" or (result["help"]["exit_code"] == 0 and not result["help"]["missing_flags"]))
    if args.json:
        _print_json(dict(result, ok=ok))
    else:
        print("%s（%s，来源 %s）：%s" % (args.runtime_id, adapter, source, version or "版本未知"))
        if adapter == "pi":
            missing = result["help"]["missing_flags"]
            print("  缺少的参数：%s" % ("、".join(missing) if missing else "无"))
            print("  思考级别：%s" % "、".join(result["help"]["thinking_levels"]))
    return EXIT_OK if ok else EXIT_FAIL


# --- models ----------------------------------------------------------------

def cmd_models(args: Any) -> int:
    return _run(_models, args)


def _models(args: Any) -> int:
    _kc_, repo, config = _open(args)
    adapter = _adapter_of(config, args.runtime)
    if adapter is None:
        raise _error("没有登记 runtime %s（或它的 adapter 无效）" % _shown(args.runtime))
    if not ADAPTERS[adapter]["list_models"]:
        raise _error("%s 适配器列不出模型（本轮只有 pi 支持 --list-models）" % adapter)
    command, _source, lines = runtime_command(repo, config, args.runtime)
    for line in lines:
        print(line, file=sys.stderr)
    if command is None:
        raise _error("找不到 runtime %s 的命令" % args.runtime)
    pd.ensure_argv_safe(command)
    env, _removed = pd.child_env(config)
    code, out, err = pd.run_capture(list(command) + pd.RESOURCE_FLAGS + ["--list-models"], env=env, timeout=90)
    if code != 0:
        raise _error("%s --list-models 退出码 %s：%s" % (args.runtime, code, pd.redact_secrets((err or out).strip())[:200]))
    allowed = [entry for entry in config.get("allowed_executors") or [] if isinstance(entry, dict)] \
        if isinstance(config.get("allowed_executors"), list) else []
    # CLI 的输出按整行判断疑似凭据，跨列的写法也算：有就整行遮掉；允许列表仍按原值比较（闸二第 4 片 B2）
    rows = [{"provider": "<redacted>" if secret else provider, "model": "<redacted>" if secret else model,
             "allowed": any(entry.get("provider") == provider and entry.get("model") == model for entry in allowed)
             if allowed else None} for provider, model, secret in pd.list_models_lines(out)]
    if args.json:
        _print_json({"runtime": args.runtime, "models": rows, "allowed_executors_set": bool(allowed)})
        return EXIT_OK
    if not rows:
        print("没有可用的模型（%s）" % (pd.list_models_empty_reason(out) or "输出里没有表格"))
    for row in rows:
        mark = "不限制" if row["allowed"] is None else ("在允许列表" if row["allowed"] else "不在允许列表")
        print("%-20s %-36s %s" % (row["provider"], row["model"], mark))
    return EXIT_OK


# --- profile ---------------------------------------------------------------

def cmd_profile(args: Any) -> int:
    return _run({"show": _profile_show, "add": _profile_add, "edit": _profile_edit,
                 "remove": _profile_remove}[args.profile_action], args)


def _split_model(text: str) -> Tuple[str, str]:
    provider, _slash, model = str(text).partition("/")
    if not provider or not model:
        raise _error("--model 写成 <provider>/<模型 ID>：%s" % _shown(text), EXIT_USAGE)
    return provider, model


def _profile_show(args: Any) -> int:
    _kc_, _repo_, config = _open(args)
    items = [(profile_id, spec) for profile_id, spec in _entries(_mapping(config, "profiles"))
             if args.profile_id is None or profile_id == args.profile_id]
    if args.profile_id is not None and not items:
        raise _error("没有 profile %s" % _shown(args.profile_id))
    rows = []
    for profile_id, spec in items:
        spec = spec if isinstance(spec, dict) else {}
        model = spec.get("model") if isinstance(spec.get("model"), dict) else {}
        options = spec.get("options") if isinstance(spec.get("options"), dict) else {}
        rows.append({"id": profile_id, "runtime": spec.get("runtime"), "adapter": _adapter_of(config, spec.get("runtime")),
                     "provider": model.get("provider"), "model": model.get("id"), "options": options,
                     "credential_env": spec.get("credential_env", [])})
    if args.json:
        _print_json({"profiles": rows})
        return EXIT_OK
    if not rows:
        print("还没有 profile：config profile add <id> --runtime <r> --model <provider/模型>")
    for row in rows:
        thinking = row["options"].get("thinking", pd.DEFAULT_THINKING if row["adapter"] == "pi" else None)
        print("%-16s runtime %s（%s）  %s/%s%s  凭据变量 %s" % (
            row["id"], row["runtime"], row["adapter"] or "未登记", row["provider"], row["model"],
            " · thinking %s" % thinking if thinking else "", "、".join(row["credential_env"]) or "无"))
    return EXIT_OK


def _profile_add(args: Any) -> int:
    kc = _kc()
    repo = kc._repo(args.repo)
    if not _id_ok(args.profile_id):
        raise _error("profile ID 不合法（小写字母、数字与连字符）：%s" % _shown(args.profile_id), EXIT_USAGE)
    provider, model = _split_model(args.model)
    with kc.config_transaction(repo, "profile.add", args.profile_id, confirm=args.yes) as txn:
        config = txn.config
        profiles = dict(_mapping(config, "profiles"))
        if args.profile_id in profiles:
            raise _error("profile %s 已存在：改用 config profile edit" % args.profile_id)
        spec: Dict[str, Any] = {"runtime": args.runtime, "model": {"provider": provider, "id": model}}
        if args.thinking is not None:
            spec["options"] = {"thinking": args.thinking}
        if args.credential_env:
            spec["credential_env"] = list(args.credential_env)
        profiles[args.profile_id] = spec
        config["profiles"] = profiles
        txn.publish(config)  # 整份校验（D1）；不运行任何 CLI（M9）
    print("已添加 profile %s" % args.profile_id)
    return EXIT_OK


def _profile_edit(args: Any) -> int:
    if args.model is None and args.thinking is None and args.credential_env is None and args.runtime is None:
        raise _error("profile edit 至少给一项：--model、--thinking、--credential-env 或 --runtime", EXIT_USAGE)
    kc = _kc()
    repo = kc._repo(args.repo)
    with kc.config_transaction(repo, "profile.edit", args.profile_id, confirm=args.yes) as txn:
        config = txn.config
        profiles = dict(_mapping(config, "profiles"))
        spec = profiles.get(args.profile_id)
        if not isinstance(spec, dict) or str(args.profile_id).startswith("_"):
            raise _error("没有 profile %s" % _shown(args.profile_id))
        spec = json.loads(json.dumps(spec))
        if args.runtime is not None:
            spec["runtime"] = args.runtime
        if args.model is not None:
            provider, model = _split_model(args.model)
            spec["model"] = {"provider": provider, "id": model}
        if args.thinking is not None:
            options = spec.get("options") if isinstance(spec.get("options"), dict) else {}
            spec["options"] = dict(options, thinking=args.thinking)
        if args.credential_env is not None:
            spec["credential_env"] = list(args.credential_env)
        profiles[args.profile_id] = spec
        config["profiles"] = profiles
        changed = txn.publish(config)  # 非法的修改整份校验不过，不写（M4）；改变生效绑定时按 D8 要确认
    print("%s profile %s" % ("已修改" if changed else "没有变化：", args.profile_id))
    return EXIT_OK


def _profile_users(config: Dict[str, Any], profile_id: str) -> List[str]:
    users = ["roles.%s" % role for role, binding in _entries(_mapping(config, "roles"))
             if isinstance(binding, dict) and binding.get("profile") == profile_id]
    users += ["hub_roles.%s.%s" % (post, field) for post, binding in _entries(_mapping(config, "hub_roles"))
              for field in HUB_BINDING_KEYS if isinstance(binding, dict) and binding.get(field) == profile_id]
    for name, spec in _entries(_mapping(config, "presets")):
        roles = spec.get("roles") if isinstance(spec, dict) and isinstance(spec.get("roles"), dict) else {}
        users += ["presets.%s.roles.%s" % (name, role) for role, binding in _entries(roles)
                  if isinstance(binding, dict) and binding.get("profile") == profile_id]
    return users


def _profile_remove(args: Any) -> int:
    kc = _kc()
    repo = kc._repo(args.repo)
    with kc.config_transaction(repo, "profile.remove", args.profile_id, confirm=args.yes) as txn:
        config = txn.config
        profiles = dict(_mapping(config, "profiles"))
        if args.profile_id not in profiles or str(args.profile_id).startswith("_"):
            raise _error("没有 profile %s" % _shown(args.profile_id))
        users = _profile_users(config, args.profile_id)
        if users:
            raise _error("profile %s 被 %s 引用：先改这些绑定或方案" % (args.profile_id, "、".join(users)))
        del profiles[args.profile_id]
        if profiles:
            config["profiles"] = profiles
        else:
            config.pop("profiles", None)
        txn.publish(config)
    print("已删除 profile %s" % args.profile_id)
    return EXIT_OK


# --- role ------------------------------------------------------------------

def cmd_role(args: Any) -> int:
    return _run({"show": _role_show, "set": _role_set}[args.role_action], args)


def _role_rows(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    explicit = _mapping(config, "roles")
    active = config.get("active_preset") if isinstance(config.get("active_preset"), str) else None
    presets = _mapping(config, "presets")
    preset_roles = presets.get(active, {}).get("roles", {}) if active and isinstance(presets.get(active), dict) else {}
    preset_roles = preset_roles if isinstance(preset_roles, dict) else {}
    rows = []
    for role in ROLES:
        binding = effective_binding(config, role)
        row: Dict[str, Any] = {"role": role, "explicit": role in explicit, "binding": binding,
                               "differs_from_preset": role in preset_roles and preset_roles.get(role) != explicit.get(role)}
        if binding is not None and binding.get("mode") == "headless":
            _mode, profile_id, runtime, adapter, provider, model, thinking = binding_tuple(config, role)
            row.update(profile=profile_id, runtime=runtime, adapter=adapter, provider=provider, model=model,
                       thinking=thinking, connected=adapter is not None and role in ADAPTERS[adapter]["headless_roles"])
        rows.append(row)
    return rows


def _role_text(row: Dict[str, Any]) -> str:
    binding = row["binding"]
    if binding is None:
        return "由合同决定（没有写 roles.%s）" % row["role"]
    mode = binding.get("mode")
    if mode == "headless":
        return "headless · profile %s（runtime %s，%s）%s/%s · thinking %s%s" % (
            row.get("profile"), row.get("runtime"), row.get("adapter") or "未登记", row.get("provider"),
            row.get("model"), row.get("thinking"), "" if row.get("connected") else " · 本轮未接通")
    if mode == "interactive_host":
        return "interactive_host%s（交互宿主的模型不由 Themis 切换）" % (" · %s" % binding["host"] if binding.get("host") else "")
    return str(mode)


def _role_show(args: Any) -> int:
    _kc_, _repo_, config = _open(args)
    rows = _role_rows(config)
    active = config.get("active_preset") if isinstance(config.get("active_preset"), str) else None
    if args.json:
        _print_json({"active_preset": active, "roles": rows})
        return EXIT_OK
    print("当前方案：%s" % (active or "无"))
    for row in rows:
        print("%-16s %s%s" % (row["role"], _role_text(row), "  ← 与方案 %s 不一致" % active if row["differs_from_preset"] else ""))
    return EXIT_OK


def _binding_warnings(config: Dict[str, Any], role: str) -> List[str]:
    """role set 之后的提示（不阻止写入）：适配器本轮没有接通这个角色；执行模型不在 allowed_executors 里。"""
    binding = effective_binding(config, role)
    if binding is None or binding.get("mode") != "headless":
        return []
    _mode, profile_id, _runtime, adapter, provider, model, thinking = binding_tuple(config, role)
    warnings = []
    if adapter is None or role not in ADAPTERS[adapter]["headless_roles"]:
        warnings.append("%s 绑定到 %s：这个适配器本轮没有接通 %s，按角色写的合同不会派遣" % (role, adapter or "未登记的 runtime", role))
    problem = pd.allowed_executor_check(config, provider, model, thinking) if role in ("execution", "contract") else None
    if problem is not None and problem[0] == "missing":  # 与内核同一个判定（闸二总复核 S3）
        warnings.append("profile %s 的 %s/%s 不在 allowed_executors 里，prepare 会拒绝" % (profile_id, provider, model))
    elif problem is not None:
        warnings.append("allowed_executors 把 %s/%s 的思考级别固定为 %s，profile %s 是 %s，prepare 会拒绝"
                        % (provider, model, problem[1], profile_id, thinking))
    return warnings


def _role_set(args: Any) -> int:
    if args.role not in ROLES:
        raise _error("角色只能是 %s 之一" % "、".join(ROLES), EXIT_USAGE)
    if args.target in MODE_WORDS:
        binding: Dict[str, Any] = {"mode": args.target}
        if args.host is not None:
            if args.target != "interactive_host":
                raise _error("--host 只用于 interactive_host", EXIT_USAGE)
            binding["host"] = args.host
        if args.cadence_seconds is not None:
            raise _error("--cadence-seconds 只用于 scheduler_agent 的 headless 绑定", EXIT_USAGE)
    else:
        if args.host is not None:
            raise _error("--host 只用于 interactive_host", EXIT_USAGE)
        binding = {"mode": "headless", "profile": args.target}
        if args.cadence_seconds is not None:
            if args.role != "scheduler_agent":
                raise _error("--cadence-seconds 只用于 scheduler_agent", EXIT_USAGE)
            binding["cadence_seconds"] = args.cadence_seconds
    kc = _kc()
    repo = kc._repo(args.repo)
    with kc.config_transaction(repo, "role.set", args.role, confirm=args.yes) as txn:
        config = txn.config
        roles = dict(_mapping(config, "roles"))
        roles[args.role] = binding
        config["roles"] = roles
        changed = txn.publish(config)  # 模式与角色是否相配、profile 是否登记都在整份校验里（D1）
    print("%s roles.%s = %s" % ("已设置" if changed else "没有变化：", args.role, json.dumps(binding, ensure_ascii=False)))
    for warning in _binding_warnings(config, args.role):
        print("WARN  %s" % warning)
    return EXIT_OK


# --- hub（七端的岗位绑定，r3 第 154 轮）-----------------------------------------

def cmd_hub(args: Any) -> int:
    return _run({"show": _hub_show, "set": _hub_set, "unset": _hub_unset}[args.hub_action], args)


def _hub_rows(config: Dict[str, Any], agent_dir: Path) -> List[Dict[str, Any]]:
    rows = []
    for post in HUB_POSTS:
        binding = hub_binding(config, post)
        row: Dict[str, Any] = {"post": post, "source": "default" if binding is None else "config",
                               "allowed_adapters": list(HUB_POST_ADAPTERS[post])}
        row.update(dict(HUB_DEFAULTS[post], profile=None, runtime=None) if binding is None else binding)
        row["turn"] = _hub_turn(post, row["adapter"])
        row["last_turn"] = _hub_last_turn(agent_dir, post)
        rows.append(row)
    return rows


def _hub_turn(post: str, adapter: Any) -> Optional[Dict[str, Any]]:
    """这个岗位一回合拿到的（模型配置 §6 第二条，r3 第 168 轮）：时限、工具面，绑在 quizs 上时还有每回合的预算。执行端是 None。"""
    if post not in HUB_TURN_LIMITS:
        return None
    timeout, tools = HUB_TURN_LIMITS[post]
    budgets = None
    if adapter == "quizs":
        budgets = dict(QUIZS_VIEW_BUDGETS if post in QUIZS_VIEW_POSTS else QUIZS_TURN_BUDGETS)
    return {"timeout_seconds": timeout, "tools": list(tools), "budgets": budgets}


def _hub_last_turn(agent_dir: Path, post: str) -> Optional[Dict[str, Any]]:
    """这个岗位最近一个跑完的回合实际拿到了什么（r3 第 168 轮）：信箱的回合目录名以开始时刻开头，倒着找第一个有 result.json 的。
    档位三值照 Quizs 的写法：要求、映射（只有 quizs 回报）、生效（pi 与 claude 回报的；quizs 要提供方回报了才有）。
    第 168 轮之前的记录没有 adapter 与 effort_mapped，两项是 None。没有信箱、没跑完过、读不出时整项是 None；执行端不看"""
    if post not in HUB_POST_AGENTS:
        return None
    where = agent_dir / "mailbox" / "turns" / HUB_POST_AGENTS[post][0]
    try:
        if not _plain_dir(where):
            return None
        done = next((turn / "result.json" for turn in sorted(where.iterdir(), reverse=True)
                     if _lstat(turn / "result.json") is not None), None)
        record = None if done is None else json.loads(done.read_bytes().decode("utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(record, dict):
        return None
    adapter = record.get("adapter")
    return {"at": record.get("finished_at"), "adapter": "claude-code" if adapter == "claude" else adapter,
            "models": record.get("models"), "profile": record.get("binding_profile"),
            "thinking": {"requested": record.get("effort_requested"), "mapped": record.get("effort_mapped"),
                         "effective": record.get("effort_effective")},
            "fallback": record.get("quizs_fallback")}


def _hub_text(row: Dict[str, Any]) -> str:
    def one(spec: Dict[str, Any]) -> str:
        model = "%s/%s" % (spec.get("provider"), spec.get("model")) if spec.get("provider") else str(spec.get("model"))
        named = "profile %s，" % spec["profile"] if spec.get("profile") else ""
        return "%s%s %s · thinking %s" % (named, spec.get("adapter") or "未登记", model, spec.get("thinking"))
    text = one(row) + ("；替补 " + one(row["fallback"]) if row.get("fallback") else "")
    return text + ("" if row["source"] == "config" else "（内核缺省）")


def _hub_show(args: Any) -> int:
    _kc_, repo, config = _open(args)
    rows = _hub_rows(config, repo.agent_dir)
    if args.json:
        _print_json({"posts": rows})
        return EXIT_OK
    for row in rows:
        print("%-12s %s" % (row["post"], _hub_text(row)))
    return EXIT_OK


def _hub_post(args: Any) -> str:
    if args.post not in HUB_POSTS:
        raise _error("岗位只能是 %s 之一" % "、".join(HUB_POSTS), EXIT_USAGE)
    return args.post


def _hub_warnings(config: Dict[str, Any], post: str) -> List[str]:
    """合同端与审核端用同一个模型时给一条警告，不拦（模型配置第 8 节第 2 条）；只在改的是这两个岗位之一时说。"""
    if post not in ("contract", "audit"):
        return []
    contract, audit = hub_side(config, "contract"), hub_side(config, "audit")
    if (contract["provider"], contract["model"]) != (audit["provider"], audit["model"]):
        return []
    return ["合同端与审核端用的是同一个模型（%s/%s）：审核少一层独立性；照样生效" % (contract["provider"], contract["model"])]


def _hub_set(args: Any) -> int:
    post = _hub_post(args)
    binding: Dict[str, Any] = {"profile": args.profile}
    if args.fallback is not None:
        binding["fallback"] = args.fallback
    kc = _kc()
    repo = kc._repo(args.repo)
    with kc.config_transaction(repo, "hub.set", post, confirm=args.yes) as txn:
        config = txn.config
        hub_roles = dict(_mapping(config, "hub_roles"))
        hub_roles[post] = binding
        config["hub_roles"] = hub_roles
        changed = txn.publish(config)  # profile 是否登记、适配器许不许、替补合不合规都在整份校验里
    print("%s hub_roles.%s = %s" % ("已设置" if changed else "没有变化：", post, json.dumps(binding, ensure_ascii=False)))
    for warning in _hub_warnings(config, post):
        print("WARN  %s" % warning)
    return EXIT_OK


def _hub_unset(args: Any) -> int:
    post = _hub_post(args)
    kc = _kc()
    repo = kc._repo(args.repo)
    with kc.config_transaction(repo, "hub.unset", post, confirm=args.yes) as txn:
        config = txn.config
        hub_roles = dict(_mapping(config, "hub_roles"))
        hub_roles.pop(post, None)
        if hub_roles:
            config["hub_roles"] = hub_roles
        else:
            config.pop("hub_roles", None)
        changed = txn.publish(config)
    print("%s：hub_roles.%s 回到内核缺省" % ("已取消" if changed else "没有变化", post))
    for warning in _hub_warnings(config, post):
        print("WARN  %s" % warning)
    return EXIT_OK


# --- quizs（Quizs 的只读事实，r3 第 165 轮）-------------------------------------

#: 与 kit_hub 的 QUIZS_LIVE_ROOT、QUIZS_LIVE_NAMES、QUIZS_LIVE_FILES、QUIZS_PROFILE_IDS 和 resolve_quizs_command 相同（tests/test_kit_hub.py
#: 有一条核对）：config quizs 要在没装 kit_hub.py 的仓库里也能用，所以这里另放一份
QUIZS_LIVE_ROOT = "quizs-live"
QUIZS_LIVE_NAMES = ("plan.json", "profile.json", "qualification.json")
QUIZS_LIVE_ENV = ("QUIZS_LIVE_PLAN", "QUIZS_PROVIDER_PROFILE", "QUIZS_QUALIFICATION")
QUIZS_PROFILE_IDS = {"deepseek": "deepseek-api", "minimax": "minimax-m-plan", "stepfun": "stepfun-cn-step-plan"}
#: Quizs 两条只读命令（Quizs 的 M2，54f3438）输出的 schema_version、live status 的五种 state，每次的时限（秒）
QUIZS_PROVIDERS_SCHEMA, QUIZS_LIVE_SCHEMA, QUIZS_TIMEOUT = "quizs.providers.v1", "quizs.live-status.v1", 30
QUIZS_LIVE_STATES = ("ready", "expired", "build_mismatch", "invalid", "missing")


def quizs_command() -> List[str]:
    """quizs 的命令：QUIZS_CMD 是 JSON 的字符串列表，缺省是 PATH 里的 quizs。与 hub 一样不认配置中心登记的 quizs 运行时；
    QUIZS_CMD 不是 JSON 时 hub 冒堆栈，这里报错。"""
    raw = os.environ.get("QUIZS_CMD")
    if not raw:
        return [shutil.which("quizs") or "quizs"]
    try:
        value = json.loads(raw)
    except ValueError:
        value = None
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
        raise _error("QUIZS_CMD 要是非空的字符串列表（JSON）")
    return value


def cmd_quizs(args: Any) -> int:
    return _run({"providers": _quizs_providers, "live": _quizs_live}[args.quizs_action], args)


def _quizs_json(command: List[str], words: List[str], env: Dict[str, str],
                schema: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """跑一条 Quizs 的只读命令（不读凭据、不发请求），交回（输出的 JSON 对象，问题）。起不来、超时、退出码不是 0、输出不是
    这个 schema_version 的对象时对象是 None，问题里带退出码与脱敏之后的最后一行（截到 200 个字）。"""
    code, out, err = pd.run_capture(command + words, env=env, timeout=QUIZS_TIMEOUT)
    if code == 0:
        try:
            data = json.loads(out)
        except ValueError:
            data = None
        if isinstance(data, dict) and data.get("schema_version") == schema:
            return data, None
    lines = [line.strip() for line in pd.redact_secrets(err if code else out).splitlines() if line.strip()]
    detail = "退出码 %d" % code if code else "输出不是 %s 的 JSON 对象" % schema
    return None, "quizs %s 失败（%s）%s" % (" ".join(words[:2]), detail, "：" + lines[-1][:200] if lines else "")


def _quizs_providers(args: Any) -> int:
    _kc_, _repo_, config = _open(args)
    env, _removed = pd.child_env(config)
    data, problem = _quizs_json(quizs_command(), ["providers", "list"], env, QUIZS_PROVIDERS_SCHEMA)
    providers = None if data is None else data.get("providers")
    if data is None or not isinstance(providers, list) or not all(isinstance(item, dict) for item in providers):
        raise _error(problem or "quizs providers list 给的 providers 不是对象的列表")
    if args.json:
        _print_json({"build_id": data.get("build_id"), "providers": providers})
        return EXIT_OK
    if not providers:
        print("quizs providers list 没有列出提供方")
    for item in providers:
        thinking = item.get("thinking")
        print("%-10s %-22s %-16s %s" % (item.get("provider"), item.get("id"), item.get("model"),
                                        "、".join(str(level) for level in thinking) if isinstance(thinking, list) else thinking))
    return EXIT_OK


def _quizs_live_sets(root: Path) -> List[Dict[str, Any]]:
    """各套 live 文件：信箱 quizs-live/ 下的每个目录（目录名就是提供方，按名字排），再加环境变量给的那一套（hub 在信箱的那套
    不全时退回它；三个变量都没设就没有）。quizs live status 只认一个目录：三个变量不全、三份不在同一个目录或不叫那三个名字时只记问题。"""
    folder = root / ".agent" / "mailbox" / QUIZS_LIVE_ROOT
    names = sorted(entry.name for entry in folder.iterdir() if entry.is_dir()) if folder.is_dir() else []
    sets: List[Dict[str, Any]] = [{"source": "mailbox", "provider": name, "live_dir": str(folder / name), "problem": None}
                                  for name in names]
    given = [os.environ.get(name) or "" for name in QUIZS_LIVE_ENV]
    if not any(given):
        return sets
    row: Dict[str, Any] = {"source": "env", "provider": None, "live_dir": None, "problem": None}
    paths = [Path(value) for value in given]
    if not all(given):
        row["problem"] = "没有设 %s" % "、".join(name for name, value in zip(QUIZS_LIVE_ENV, given) if not value)
    elif len({str(path.parent) for path in paths}) > 1 or tuple(path.name for path in paths) != QUIZS_LIVE_NAMES:
        row["problem"] = "环境给的三份 live 文件不在同一个目录或不叫 %s：quizs live status 只认一个目录" % "、".join(QUIZS_LIVE_NAMES)
    else:
        row["live_dir"] = str(paths[0].parent)
    return sets + [row]


def _quizs_provider_of(status: Dict[str, Any]) -> Optional[str]:
    profile = status.get("profile")
    profile_id = profile.get("id") if isinstance(profile, dict) else None
    return next((name for name, known in QUIZS_PROFILE_IDS.items() if known == profile_id), None)


def _quizs_live(args: Any) -> int:
    _kc_, repo, config = _open(args)
    env, _removed = pd.child_env(config)
    command = quizs_command()
    rows = []
    for row in _quizs_live_sets(repo.root):
        status = None
        if row["live_dir"] is not None:
            status, row["problem"] = _quizs_json(command, ["live", "status", "--live-dir", row["live_dir"]], env, QUIZS_LIVE_SCHEMA)
        if status is not None and status.get("state") not in QUIZS_LIVE_STATES:
            status, row["problem"] = None, "quizs live status 给的 state 不认得：%s" % _shown(status.get("state"))
        if row["provider"] is None and status is not None:
            row["provider"] = _quizs_provider_of(status)
        rows.append(dict(row, status=status))
    if args.json:
        _print_json({"live": rows})
        return EXIT_OK
    if not rows:
        print("没有 live 文件：信箱的 %s/ 下没有目录，也没有设 %s" % (QUIZS_LIVE_ROOT, "、".join(QUIZS_LIVE_ENV)))
    for row in rows:
        status = row["status"] or {}
        print(("%-10s %-8s %-15s %s" % (row["provider"] or "?", row["source"], status.get("state") or "读不出",
                                        row["live_dir"] or "")).rstrip())
        missing = status.get("missing")
        note = row["problem"] or ("缺 " + "、".join(str(name) for name in missing) if isinstance(missing, list) and missing
                                  else status.get("problem"))
        if note:
            print("  %s" % note)
    return EXIT_OK


# --- preset ----------------------------------------------------------------

def cmd_preset(args: Any) -> int:
    return _run({"list": _preset_list, "show": _preset_show, "save": _preset_save, "use": _preset_use,
                 "diff": _preset_diff, "remove": _preset_remove}[args.preset_action], args)


def _preset_roles(presets: Dict[str, Any], name: str) -> Dict[str, Any]:
    spec = presets.get(name) if not str(name).startswith("_") else None
    if not isinstance(spec, dict) or not isinstance(spec.get("roles"), dict):
        raise _error("没有方案 %s" % _shown(name))
    return {role: binding for role, binding in _entries(spec["roles"])}


def _preset_list(args: Any) -> int:
    _kc_, _repo_, config = _open(args)
    active = config.get("active_preset")
    rows = [{"name": name, "description": spec.get("description") if isinstance(spec, dict) else None,
             "roles": sorted(role for role, _binding in _entries(spec.get("roles", {})))
             if isinstance(spec, dict) and isinstance(spec.get("roles"), dict) else [], "active": name == active}
            for name, spec in _entries(_mapping(config, "presets"))]
    if args.json:
        _print_json({"active_preset": active, "presets": rows})
        return EXIT_OK
    if not rows:
        print("还没有方案：config preset save <名>")
    for row in rows:
        print("%s %-16s %s  %s" % ("*" if row["active"] else " ", row["name"], "、".join(row["roles"]),
                                   row["description"] or ""))
    return EXIT_OK


def _preset_show(args: Any) -> int:
    _kc_, _repo_, config = _open(args)
    roles = _preset_roles(_mapping(config, "presets"), args.name)
    current = _mapping(config, "roles")
    active = config.get("active_preset") == args.name
    rows = [{"role": role, "binding": binding, "current": current.get(role), "differs": current.get(role) != binding}
            for role, binding in sorted(roles.items())]
    if args.json:
        _print_json({"name": args.name, "active": active, "roles": rows})
        return EXIT_OK
    print("方案 %s%s" % (args.name, "（当前在用）" if active else ""))
    for row in rows:
        print("  %-16s %s%s" % (row["role"], json.dumps(row["binding"], ensure_ascii=False),
                                "  ← 当前绑定与它不一致" if row["differs"] and active else ""))
    return EXIT_OK


def _preset_save(args: Any) -> int:
    if not _id_ok(args.name):
        raise _error("方案名不合法（小写字母、数字与连字符）：%s" % _shown(args.name), EXIT_USAGE)
    kc = _kc()
    repo = kc._repo(args.repo)
    with kc.config_transaction(repo, "preset.save", args.name, confirm=args.yes) as txn:
        config = txn.config
        roles = _mapping(config, "roles")
        selected = [role.strip() for role in args.roles.split(",") if role.strip()] if args.roles \
            else [role for role in ROLES if role in roles]
        unknown = [role for role in selected if role not in ROLES]
        if unknown:
            raise _error("未知角色：%s（只有 %s）" % ("、".join(_shown(role) for role in unknown), "、".join(ROLES)), EXIT_USAGE)
        missing = [role for role in selected if role not in roles]
        if missing:
            raise _error("这些角色还没有写出绑定：%s（先 config role set）" % "、".join(missing))
        if not selected:
            raise _error("roles 里还没有绑定可存：先 config role set")
        presets = dict(_mapping(config, "presets"))
        if args.name in presets and not args.force:
            raise _error("方案 %s 已存在：要覆盖加 --force" % args.name)
        spec: Dict[str, Any] = {"roles": {role: json.loads(json.dumps(roles[role])) for role in selected}}
        if args.description is not None:
            spec["description"] = args.description
        presets[args.name] = spec
        config["presets"] = presets
        txn.publish(config)
    print("已保存方案 %s：%s" % (args.name, "、".join(selected)))
    return EXIT_OK


def _role_contract_versions(repo: Any) -> List[Tuple[str, str]]:
    """按角色写的合同版本与它们的记录状态（D8 的影响说明）：[(task.vN, 状态)]。只读合同与记录。"""
    rows: List[Tuple[str, str]] = []
    plans = repo.plans_dir
    try:
        paths = sorted(plans.glob("*.v*.json")) if plans.is_dir() else []
    except OSError:
        return rows
    for path in paths:
        try:
            raw = json.loads(path.read_bytes().decode("utf-8"))
        except (OSError, ValueError):
            continue
        executor = raw.get("executor") if isinstance(raw, dict) else None
        task_id, version = raw.get("task_id") if isinstance(raw, dict) else None, \
            raw.get("plan_version") if isinstance(raw, dict) else None
        if pd.executor_class(executor) != "role" or not isinstance(task_id, str) or not pd.TASK_ID_RE.match(task_id) \
                or isinstance(version, bool) or not isinstance(version, int):
            continue
        try:
            status = "沿用版本记录" if pd.load_binding_record(repo, task_id, version) is not None else "还没有记录，会用新绑定"
        except pd.DispatchError:
            status = "版本记录无效"
        rows.append(("%s.v%d（%s）" % (task_id, version, executor.get("role")), status))
    return rows


def _preset_use(args: Any) -> int:
    kc = _kc()
    repo = kc._repo(args.repo)
    with kc.config_transaction(repo, "preset.use", args.name, confirm=args.yes) as txn:
        config = txn.config
        listed = _preset_roles(_mapping(config, "presets"), args.name)
        roles = dict(_mapping(config, "roles"))
        for role, binding in listed.items():  # 只覆盖方案里列出的角色（D8）
            roles[role] = json.loads(json.dumps(binding))
        config["roles"] = roles
        config["active_preset"] = args.name
        print("影响（写入之前）：运行中与已准备的 attempt 不受影响（执行模型在 prepare 时已固定）")
        for version, status in _role_contract_versions(repo):
            print("  %s：%s" % (version, status))
        changed = txn.publish(config)
    print("%s 方案 %s（覆盖 %s）" % ("已切换到" if changed else "没有变化：", args.name, "、".join(sorted(listed))))
    for role in sorted(listed):  # 与 role set 相同的提示（闸二第 4 片 S4）
        for warning in _binding_warnings(config, role):
            print("WARN  %s" % warning)
    return EXIT_OK


def _preset_diff(args: Any) -> int:
    _kc_, _repo_, config = _open(args)
    presets = _mapping(config, "presets")
    left, right = _preset_roles(presets, args.a), _preset_roles(presets, args.b)
    rows = [{"role": role, "a": left.get(role), "b": right.get(role), "same": left.get(role) == right.get(role)}
            for role in ROLES if role in left or role in right]
    if args.json:
        _print_json({"a": args.a, "b": args.b, "roles": rows})
        return EXIT_OK
    for row in rows:
        print("%-16s %s" % (row["role"], "相同" if row["same"] else "%s：%s  |  %s：%s" % (
            args.a, json.dumps(row["a"], ensure_ascii=False) if row["a"] is not None else "未列出",
            args.b, json.dumps(row["b"], ensure_ascii=False) if row["b"] is not None else "未列出")))
    return EXIT_OK


def _preset_remove(args: Any) -> int:
    kc = _kc()
    repo = kc._repo(args.repo)
    with kc.config_transaction(repo, "preset.remove", args.name, confirm=args.yes) as txn:
        config = txn.config
        presets = dict(_mapping(config, "presets"))
        _preset_roles(presets, args.name)
        if config.get("active_preset") == args.name:
            raise _error("方案 %s 正在用：先 preset use 别的方案，或 config unset active_preset" % args.name)
        del presets[args.name]
        if presets:
            config["presets"] = presets
        else:
            config.pop("presets", None)
        txn.publish(config)
    print("已删除方案 %s" % args.name)
    return EXIT_OK


# --- doctor（D10）-----------------------------------------------------------

def cmd_doctor(args: Any) -> int:
    return _run(_doctor, args)


def _yes_no(value: Any) -> str:
    return "不适用" if value is None else ("是" if value else "否")


def _credential_ready(env: Dict[str, str], names: Any) -> Dict[str, bool]:
    """D9：名字出现在 child_env(config) 里（按大写比较）且值非空才算可用；只判断，不输出值。"""
    present = {name.upper(): value for name, value in env.items()}
    return {name: bool(present.get(name.upper())) for name in names if isinstance(name, str)} \
        if isinstance(names, list) else {}


def _doctor(args: Any) -> int:
    _kc_, repo, config = _open(args)
    env, _removed = pd.child_env(config)
    caches: Tuple[Dict[str, Any], Dict[Any, Any]] = ({}, {})
    rows = []
    if args.record:  # 按版本记录核验：与 run 用同一条命令、同一个模型与思考级别（闸二总复核第 2 轮 S4）
        rows.append(_record_readiness(repo, config, env, caches, args.record))
    for row in _role_rows(config) if not args.record else []:
        binding = row["binding"]
        if binding is None or binding.get("mode") != "headless":
            rows.append({"role": row["role"], "mode": binding.get("mode") if binding else None, "problems": [],
                         "text": _role_text(row), "ready": True})
            continue
        rows.append(_headless_readiness(repo, config, env, caches, row))
    _print_doctor(args, rows)
    return EXIT_OK if all(row["ready"] for row in rows) else EXIT_FAIL


def _record_readiness(repo: Any, config: Dict[str, Any], env: Dict[str, str], caches: Any, plan_key: str) -> Dict[str, Any]:
    """一个合同版本的执行模型记录能不能跑：命令按 run 的顺序解析（runtime 不必仍在配置里登记），模型列表、登录与思考级别
    都用记录里的值与 child_env(config)；允许列表按当前配置判断（run 时也重新检查）。"""
    match = pd.PLAN_KEY_RE.match(str(plan_key))
    if match is None:
        raise _error("--record 写成 <task-id>.v<N>：%s" % _shown(plan_key), EXIT_USAGE)
    task_id, version = match.group("task"), int(match.group("ver"))
    record = pd.load_binding_record(repo, task_id, version)
    if record is None:
        raise _error("%s 还没有版本记录：第一次 prepare 才会建立；核验当前绑定用 config doctor" % plan_key)
    entry = {key: record[key] for key in ("role", "profile", "runtime", "adapter", "provider", "model", "thinking")}
    entry["connected"] = record["adapter"] in ADAPTERS and record["role"] in ADAPTERS[record["adapter"]]["headless_roles"]
    out = _headless_readiness(repo, config, env, caches, entry)
    out["record"] = pd.binding_record_rel(task_id, version)
    return out


def _headless_readiness(repo: Any, config: Dict[str, Any], env: Dict[str, str], caches: Any,
                        row: Dict[str, Any]) -> Dict[str, Any]:
    """一个 headless 绑定（当前绑定或版本记录）的就绪事实与问题（D10）。版本与 --help 按 runtime 缓存，模型列表与
    auth check 按（runtime, provider, model）缓存，思考级别逐个判断。"""
    by_runtime, by_model = caches
    allowed = config.get("allowed_executors")
    out: Dict[str, Any] = {"role": row["role"], "mode": "headless", "problems": []}
    out.update({key: row.get(key) for key in ("profile", "runtime", "adapter", "provider", "model", "thinking",
                                              "connected")})
    problems = out["problems"]
    if not row.get("connected"):
        problems.append("适配器 %s 本轮没有接通 %s" % (row.get("adapter") or "未登记", row["role"]))
    runtime = row.get("runtime")
    probe = by_runtime.get(runtime) if runtime is not None else None
    if probe is None and runtime is not None and row.get("adapter") is not None:
        command, source, lines = runtime_command(repo, config, runtime, row.get("adapter"))
        probe = {"command": command, "source": source, "notes": lines, "version": None, "version_exit_code": None}
        if command is not None:
            probe["version_exit_code"], probe["version"] = _probe_version(command, env)
            if row["adapter"] == "pi":
                probe["help"] = _probe_help(command, env)  # 版本与 --help 按 runtime 缓存（D10）
        by_runtime[runtime] = probe
    if probe is None or probe["command"] is None:
        problems.append("找不到 runtime %s 的命令" % runtime)
        probe = probe or {"command": None, "source": "missing", "notes": []}
    else:
        out.update(command=_shown_command(probe["command"]), source=probe["source"], version=probe["version"])
        relative = cwd_relative_parts(probe["command"])
        if relative:
            problems.append("命令里有相对路径（%s）：run 在 attempt 的 worktree 里运行它，这里在当前目录探测，结果代表不了 run；"
                            "写成绝对路径" % "、".join(_shown_command(relative) or []))
        if probe["version_exit_code"] != 0:
            problems.append("%s --version 退出码 %s" % (runtime, probe["version_exit_code"]))
        if row["adapter"] == "pi" and row.get("provider") and row.get("model"):
            key = (runtime, row["provider"], row["model"])
            if key not in by_model:  # 模型列表与 auth check 按（runtime, provider, model）分别运行（D10）
                by_model[key] = pd.pi_model_readiness(probe["command"], row["provider"], row["model"], None,
                                                      probe["help"]["thinking_levels"], env)
            facts, found = by_model[key]
            out["model_listed"] = facts.get("executor_model_listed")
            out["auth_ready"] = facts.get("executor_auth_check", {}).get("exit_code") == 0
            out["thinking_supported"] = row.get("thinking") in probe["help"]["thinking_levels"]
            problems.extend(found)
            if not out["thinking_supported"]:  # 思考级别逐个角色判断，不进缓存的键
                problems.append("思考级别 %s 不受本机 pi 支持" % row.get("thinking"))
            if probe["help"]["exit_code"] != 0:  # 与 runtime probe 相同（闸二第 4 片 S2）
                problems.append("%s --help 退出码 %s" % (runtime, probe["help"]["exit_code"]))
            if probe["help"]["missing_flags"]:
                problems.append("pi 缺少参数：%s" % "、".join(probe["help"]["missing_flags"]))
    out["notes"] = probe.get("notes", [])
    if row["role"] in ("execution", "contract") and allowed:  # 与内核同一个判定，含固定的 thinking（闸二总复核 S3）
        problem = pd.allowed_executor_check(config, row.get("provider"), row.get("model"), row.get("thinking"))
        out["allowed"] = problem is None
        if problem is not None and problem[0] == "missing":
            problems.append("%s/%s 不在 allowed_executors 里" % (row.get("provider"), row.get("model")))
        elif problem is not None:
            problems.append("allowed_executors 把 %s/%s 的思考级别固定为 %s，profile 是 %s" % (
                row.get("provider"), row.get("model"), problem[1], row.get("thinking")))
    else:
        out["allowed"] = None
    profiles = _mapping(config, "profiles")
    spec = profiles.get(row.get("profile")) if isinstance(profiles.get(row.get("profile")), dict) else {}
    out["credentials"] = _credential_ready(env, spec.get("credential_env", []))
    missing = [name for name, ready in out["credentials"].items() if not ready]
    if missing:
        problems.append("凭据变量不可用（被移除、没有设置或为空）：%s" % "、".join(missing))
    out["ready"] = not problems
    return out


def _print_doctor(args: Any, rows: List[Dict[str, Any]]) -> None:
    ready = all(row["ready"] for row in rows)
    if args.json:
        _print_json({"ready": ready, "roles": rows})
        return
    for row in rows:
        if "text" in row:
            print("%-16s %s" % (row["role"], row["text"]))
            continue
        if row.get("record"):
            print("版本记录 %s" % row["record"])
        print("%-16s %s · profile %s · runtime %s（%s，%s %s）· %s" % (
            row["role"], "就绪" if row["ready"] else "未就绪", row.get("profile"), row.get("runtime"),
            row.get("adapter"), row.get("source", "missing"), " ".join(row.get("command") or []) or "", row.get("version") or ""))
        print("%-16s 模型 %s/%s · thinking %s · 模型列表 %s · 登录 %s · 思考级别 %s · 允许列表 %s · 凭据 %s · %s" % (  # D10
            "", row.get("provider"), row.get("model"), row.get("thinking"), _yes_no(row.get("model_listed")),
            _yes_no(row.get("auth_ready")), _yes_no(row.get("thinking_supported")),
            "不限制" if row.get("allowed") is None else _yes_no(row.get("allowed")),
            "、".join("%s %s" % (name, "可用" if ready else "不可用") for name, ready in row["credentials"].items()) or "无",
            "已接通" if row.get("connected") else "未接通"))
        for note in row.get("notes", []):
            print("  %s" % note)
        for problem in row["problems"]:
            print("  - %s" % problem)
    print("全部就绪" if ready else "有未就绪的角色")
