#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kit_config —— Code-Kit 的配置管理器（2.7.0）：看、改、校验 `.agent/dispatch.config.json`，开关决策模式，存取凭据。

用法（也可以写成 `bash scripts/dispatch-pi.sh config …`，调度器会转发到这里）：
  python scripts/kit_config.py show [--json]            每个键的生效值、来源与说明；决策模式与原因；凭据的来源（不报值）
  python scripts/kit_config.py validate                 整份校验（复用调度器各键自己的校验），有错退出 1
  python scripts/kit_config.py set <键路径> <值>        例如 set decisions.mode shadow、set kill_grace_seconds 20、
                                                        set release_check.allow '["tests/fixtures/**:home path"]'
  python scripts/kit_config.py unset <键路径>
  python scripts/kit_config.py init                     从 kit 的 dispatch.config.example.json 生成，已存在则拒绝
  python scripts/kit_config.py decisions off|shadow|on  等于 set decisions.mode
  python scripts/kit_config.py decisions marker on|off  建或删 .agent/DECISIONS_OFF（存在就一票否决）
  python scripts/kit_config.py secret set <环境变量名> [--tty] [--no-browser] [--timeout 秒] [--verify]
                                                        一次性本机网页（或 --tty 隐藏输入）把值直接存进凭据库；
                                                        规划端只看到 {"stored": true, "verified": …} 一行
  python scripts/kit_config.py secret check <环境变量名>  在哪一层找到（env / credential_store / file / none）
  python scripts/kit_config.py secret remove <环境变量名>

值的写法：先按 JSON 解析，解析不了的按字符串；键路径最多两层（`release_check.allow`、`decisions.mode`）。
写回原子：读原文件、改、整份校验、写临时文件再替换；以下划线开头的说明键与键顺序保留。
本工具不打印、不记录任何凭据的值；凭据库见 codekit/secrets.py。只依赖标准库。
"""
from __future__ import annotations

import argparse
import getpass
import html
import json
import os
import secrets as _secrets
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple
from urllib.parse import parse_qs

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import pi_dispatch as pd  # noqa: E402

try:
    from codekit import decisions as _decisions
    from codekit import plugins as _plugins
    from codekit import secrets as _store
except ModuleNotFoundError:  # pragma: no cover - the package sits next to this file in the kit
    from scripts.codekit import decisions as _decisions  # type: ignore[no-redef]
    from scripts.codekit import plugins as _plugins  # type: ignore[no-redef]
    from scripts.codekit import secrets as _store  # type: ignore[no-redef]

TOOL_VERSION = pd.TOOL_VERSION
EXIT_OK, EXIT_FAIL, EXIT_USAGE = 0, 1, 2
CONFIG_NAME = "dispatch.config.json"
EXAMPLE_NAME = "dispatch.config.example.json"
MAX_BODY = 8192
PAGE_TIMEOUT = 600.0


class ConfigError(Exception):
    def __init__(self, message: str, code: int = EXIT_FAIL) -> None:
        super().__init__(message)
        self.code = code


# ---------------------------------------------------------------------------
# 键的登记：说明、缺省、校验（复用调度器的函数）
# ---------------------------------------------------------------------------

def _check_allowed_executors(config: Dict[str, Any], _repo: Any) -> None:
    value = config.get("allowed_executors")
    if value is None:
        return
    if not isinstance(value, list):
        raise ConfigError("allowed_executors 必须是数组")
    for index, item in enumerate(value):
        if not isinstance(item, dict) or not isinstance(item.get("provider"), str) or not isinstance(item.get("model"), str):
            raise ConfigError("allowed_executors[%d] 必须是 {provider, model[, thinking]}" % index)
        for field in ("provider", "model"):
            if not pd.MODEL_TOKEN_RE.match(item[field]):
                raise ConfigError("allowed_executors[%d].%s 不是合法的标识：%r" % (index, field, item[field]))
        thinking = item.get("thinking")
        if thinking is not None and thinking not in pd.FALLBACK_THINKING_LEVELS:
            raise ConfigError("allowed_executors[%d].thinking 必须是 %s 之一" % (index, "/".join(pd.FALLBACK_THINKING_LEVELS)))
        unknown = set(item) - {"provider", "model", "thinking"}
        if unknown:
            raise ConfigError("allowed_executors[%d] 有未知键：%s" % (index, ", ".join(sorted(unknown))))


def _check_worktree_root(config: Dict[str, Any], repo: Any) -> None:
    value = config.get("worktree_root")
    if value is not None and not isinstance(value, str):
        raise ConfigError("worktree_root 必须是路径字符串或 null")
    if repo is not None:
        try:
            repo.worktree_root(config)
        except pd.DispatchError as exc:
            raise ConfigError(str(exc))


def _check_kill_grace(config: Dict[str, Any], _repo: Any) -> None:
    value = config.get("kill_grace_seconds", 15)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < float(value) <= 600:
        raise ConfigError("kill_grace_seconds 必须是 0 到 600 之间的秒数")


def _check_patterns(key: str) -> Callable[[Dict[str, Any], Any], None]:
    def check(config: Dict[str, Any], _repo: Any) -> None:
        value = config.get(key, [])
        if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
            raise ConfigError("%s 必须是仓库相对 glob 的数组" % key)
        for item in value:
            problem = pd.pattern_error(item)
            if problem:
                raise ConfigError("%s 的 %r：%s" % (key, item, problem))
    return check


def _check_via(function: Callable[[Dict[str, Any]], Any]) -> Callable[[Dict[str, Any], Any], None]:
    def check(config: Dict[str, Any], _repo: Any) -> None:
        try:
            function(config)
        except pd.DispatchError as exc:
            raise ConfigError(str(exc))
    return check


def _check_env_names(key: str) -> Callable[[Dict[str, Any], Any], None]:
    def check(config: Dict[str, Any], _repo: Any) -> None:
        value = config.get(key, [])
        if not isinstance(value, list) or any(not isinstance(item, str) or not pd.ENV_NAME_RE.match(item) for item in value):
            raise ConfigError("%s 必须是环境变量名的数组" % key)
    return check


def _check_release(config: Dict[str, Any], _repo: Any) -> None:
    value = config.get("release_check")
    if value is None:
        return
    if not isinstance(value, dict) or set(value) - {"allow", "denylist"}:
        raise ConfigError("release_check 只能有 allow（规则数组）与 denylist（路径）两个键")
    if "denylist" in value and not isinstance(value["denylist"], str):
        raise ConfigError("release_check.denylist 必须是路径字符串")
    try:
        pd._release_allow_rules(config, [])
    except pd.DispatchError as exc:
        raise ConfigError(str(exc))


def _check_decisions(config: Dict[str, Any], repo: Any) -> None:
    try:
        settings = _decisions.settings_from_config(config, repo.agent_dir if repo is not None else None,
                                                   pd.DECISIONS_PLUGIN_DIR)
    except _decisions.DecisionError as exc:
        raise ConfigError("decisions 无效：%s" % exc.detail)
    if settings.active:  # 2.8.0：生效时问题清单必须与插件内容锁一致，否则 prepare 也会拒绝
        link = battery_link_problem()
        if link is not None:  # 3.0 第一轮：读之前先查链接，不跟随它去读（与 plugins verify 一致）
            raise ConfigError("decisions 的问题清单经过链接（无效：链接 %s），没有读取" % link)
        try:
            _decisions.verify_battery_lock(pd.DECISIONS_PLUGIN_DIR)
        except _decisions.DecisionError as exc:
            raise ConfigError("decisions 的问题清单与插件内容锁不符：%s" % exc.detail)


def battery_link_problem() -> Optional[str]:
    """决策插件 questions/ 及其中每个 *.json 读之前的链接检查：第一个链接或 junction 的那一级，没有则 None。

    3.0 第一轮（闸二 B1）：verify_battery_lock 直接读文件、不查链接；配置校验、写入门禁与修复提示的模拟
    都先过这一关，题库经过链接时就不读。从 KIT_ROOT 往下逐级查（pd.first_link_component）。
    """
    plugin_dir = Path(pd.DECISIONS_PLUGIN_DIR)
    try:  # 按字面求相对路径，不 resolve：resolve 会顺着链接走出去，漏掉链接那一级
        base = plugin_dir.relative_to(Path(pd.KIT_ROOT)).as_posix()
    except ValueError:
        base = None
    questions = plugin_dir / "questions"
    names: List[str] = []
    try:
        if not pd.is_link_or_junction(questions) and questions.is_dir():
            names = sorted(path.name for path in questions.glob("*.json"))
    except OSError:
        names = []
    for rel in ["questions"] + ["questions/%s" % name for name in names]:
        if base is not None:
            try:
                link = pd.first_link_component(Path(pd.KIT_ROOT), "%s/%s" % (base, rel))
            except ValueError:
                return "%s/%s" % (base, rel)
            if link is not None:
                return link
        elif pd.is_link_or_junction(plugin_dir / rel):
            return str(plugin_dir / rel)
    return None


PLUGINS_SUBKEYS = ("enabled", "allowed_permissions")


def _check_plugins(config: Dict[str, Any], _repo: Any) -> None:
    """3.0 第一轮：plugins.enabled 与 plugins.allowed_permissions（决策插件读它们，codekit/decisions.py）。

    缺省就是不限制；存在时必须是列表。只校验格式，不校验是否已安装：同一份配置要在外部运行与
    安装布局下都合法，“列入但未安装”由 plugins list / verify 报告。修复提示由 validate_config 附上。
    """
    if "plugins" not in config:
        return
    value = config["plugins"]
    if not isinstance(value, dict):
        raise ConfigError("plugins 必须是对象（子键 enabled、allowed_permissions），现在是 %s" % json.dumps(value, ensure_ascii=False))
    unknown = sorted(str(key) for key in value if not (isinstance(key, str) and (key in PLUGINS_SUBKEYS or key.startswith("_"))))
    if unknown:
        raise ConfigError("plugins 有未知子键：%s（只允许 enabled、allowed_permissions 与下划线开头的说明）" % ", ".join(unknown))
    for key in PLUGINS_SUBKEYS:
        if key in value and not isinstance(value[key], list):
            raise ConfigError("plugins.%s 必须是列表，现在是 %s；不写这个子键表示不限制" % (key, json.dumps(value[key], ensure_ascii=False)))
    for index, item in enumerate(value.get("enabled", [])):
        if not isinstance(item, str) or not _plugins.PLUGIN_ID.fullmatch(item):  # match 会放过末尾的换行
            raise ConfigError("plugins.enabled[%d] 不是合法的插件 ID：%s" % (index, json.dumps(item, ensure_ascii=False)))
    for index, item in enumerate(value.get("allowed_permissions", [])):
        if not isinstance(item, str) or not item:
            raise ConfigError("plugins.allowed_permissions[%d] 必须是非空字符串：%s" % (index, json.dumps(item, ensure_ascii=False)))
    for key in PLUGINS_SUBKEYS:
        items = value.get(key, [])
        duplicates = sorted({item for item in items if items.count(item) > 1})
        if duplicates:
            raise ConfigError("plugins.%s 有重复项：%s" % (key, ", ".join(duplicates)))


def plugins_section_error(config: Dict[str, Any]) -> Optional[str]:
    """plugins 段的格式错误（与 validate_config 报的同一句，不带修复提示）；合法或缺省时为 None。

    3.0 第一轮：plugins enable / disable 在计算变化之前先查原配置，不合法就拒绝并附上
    plugins_fix_hint(原配置)——按变化之后的配置算出的提示，在原配置上未必执行得了。
    """
    try:
        _check_plugins(config, None)
    except ConfigError as exc:
        return str(exc)
    return None


#: 键 → (说明, 缺省值的文字, 校验函数)。顺序就是 show 的顺序。
KEYS: Dict[str, Tuple[str, str, Callable[[Dict[str, Any], Any], None]]] = {
    "allowed_executors": ("允许的执行模型 [{provider, model, thinking}]；为空不限制", "[]（不限制）", _check_allowed_executors),
    "worktree_root": ("worktree 的父目录（必须在仓库之外）；null 用系统临时目录下的 pi-worktrees/", "null", _check_worktree_root),
    "kill_grace_seconds": ("超时或取消后给进程树的宽限秒数", "15", _check_kill_grace),
    "check_artifact_patterns": ("检查可以产生、不算候选漂移的缓存文件（仓库相对 glob）", "[]", _check_patterns("check_artifact_patterns")),
    "extra_protected_paths": ("本仓库对执行器永远只读的路径（仓库相对模式）", "[]", _check_via(pd.extra_protected_paths)),
    "planner_paths": ("规划端自己会编辑的路径（运行期间变化只记备注）", "内置：.agent/plans/**、reviews/**、design/**、*.md", _check_via(pd.planner_paths)),
    "commit_trailers": ("branch 创建候选提交时追加的尾注 `Key: value`", "[]", _check_via(pd.commit_trailers)),
    "env_remove": ("在默认列表之外还要对执行器移除的环境变量名", "[]", _check_env_names("env_remove")),
    "env_keep": ("默认移除列表里确实要保留的环境变量名", "[]", _check_env_names("env_keep")),
    "release_check": ("release-check 的放过规则 allow（`<glob>:<模式名>`）与拒绝清单路径 denylist", "{}", _check_release),
    "pricing": ("执行模型单价（2.8.0）：<provider>/<model> → input、output、cache_read、cache_write（每 per_tokens 个 token，"
                "缺省一百万）、currency、source、as_of；metrics 用 token 乘单价估算费用。kit 不内置价格，由你填",
                "{}（不估算）", _check_via(pd.pricing_table)),
    "decisions": ("决策模型：mode（off/shadow/on）、api_key_env、base_url、model、timeout_seconds、budget_seconds、max_state_chars、points",
                  "mode off", _check_decisions),
    "plugins": ("插件的启用与权限（3.0）：enabled 插件 ID 列表，allowed_permissions 权限名列表；不写的子键表示不限制",
                "不限制", _check_plugins),
}


# ---------------------------------------------------------------------------
# 读写
# ---------------------------------------------------------------------------

def _repo(path: Optional[str]) -> Any:
    try:
        return pd.Repo.discover(path)
    except pd.DispatchError as exc:
        raise ConfigError("不在 Git 仓库里：%s" % exc, EXIT_USAGE)


def config_path(repo: Any) -> Path:
    return repo.agent_dir / CONFIG_NAME


def load_config(repo: Any) -> Dict[str, Any]:
    path = config_path(repo)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError) as exc:  # RecursionError：嵌套过深的 JSON
        raise ConfigError("无法解析 %s：%s" % (path, type(exc).__name__ if isinstance(exc, RecursionError) else exc))
    if not isinstance(data, dict):
        raise ConfigError("%s 顶层必须是对象" % path)
    return data


def validate_config(config: Dict[str, Any], repo: Any, *, hints: bool = True) -> List[str]:
    """整份校验；返回错误列表（空表示有效）。未知键是错误，下划线键是说明。

    hints 为真时，plugins 键的错误后面附上 plugins_fix_hint 给出的修复命令；plugins_fix_hint 模拟候选时
    传 hints=False，所以不会重入。
    """
    errors: List[str] = []
    for key in config:
        if not isinstance(key, str):
            errors.append("键必须是字符串")
        elif not key.startswith("_") and key not in KEYS:
            errors.append("未知键 %r（已知：%s）" % (key, ", ".join(KEYS)))
    for key, (_desc, _default, check) in KEYS.items():
        try:
            check(config, repo)
        except ConfigError as exc:
            message = str(exc)
            if key == "plugins" and hints:
                hint = plugins_fix_hint(config, repo)
                if hint:
                    message += "；修复：%s" % hint
            errors.append(message)
    return errors


def _installed_plugin_ids() -> List[str]:
    """当前布局下 KIT_ROOT/plugins/ 里的插件目录名（匹配插件 ID、不是链接），按名字排序。"""
    root = pd.KIT_ROOT / "plugins"
    if not root.is_dir() or pd.is_link_or_junction(root):
        return []
    return sorted(entry.name for entry in root.iterdir()
                  if _plugins.PLUGIN_ID.fullmatch(entry.name) and entry.is_dir() and not pd.is_link_or_junction(entry))


def plugins_fix_hint(config: Dict[str, Any], repo: Any) -> Optional[str]:
    """plugins 存在非列表的子键（或 plugins 本身不是对象）时，给出一条执行后能通过整份校验的命令；没有则 None。

    D6、D7 共用（3.0 第一轮设计）。候选依次是：删掉非法的子键；决策插件生效且题库不一致时，换成
    enabled =“当前布局全部插件减去 decisions”的合法对象（一次替换同时修好非法值并关掉决策插件）。
    每个候选先用 validate_config(…, hints=False) 模拟，通过才给出；都不通过时返回 None。
    """
    if "plugins" not in config:
        return None
    section = config["plugins"]
    if isinstance(section, dict):
        bad = [key for key in PLUGINS_SUBKEYS if key in section and not isinstance(section[key], list)]
        if not bad:
            return None
    else:
        bad = list(PLUGINS_SUBKEYS)
    candidates: List[Tuple[str, Dict[str, Any]]] = []
    removed = json.loads(json.dumps(config))
    if isinstance(section, dict) and len(bad) == 1:
        del removed["plugins"][bad[0]]
        if not removed["plugins"]:
            del removed["plugins"]
        candidates.append(("config unset plugins.%s" % bad[0], removed))
    else:
        del removed["plugins"]
        candidates.append(("config unset plugins", removed))
    replacement: Dict[str, Any] = {}
    if isinstance(section, dict):
        replacement = {key: value for key, value in section.items()
                       if key.startswith("_") or (key in PLUGINS_SUBKEYS and isinstance(value, list))}
    # 已有合法的 enabled 列表：保持原样只去掉 decisions；缺省或非法（都等于不限制）：全部已安装插件减去 decisions。
    kept = replacement.get("enabled")
    base = kept if isinstance(kept, list) else _installed_plugin_ids()
    replacement["enabled"] = [name for name in base if name != _decisions.PLUGIN_ID]
    replaced = json.loads(json.dumps(config))
    replaced["plugins"] = replacement
    # 单引号写成 JSON 的 \u0027 转义：整段放进单引号，bash 与 PowerShell 都能原样执行（闸二 S1）
    text = json.dumps(replacement, ensure_ascii=False, separators=(",", ":")).replace("'", "\\u0027")
    candidates.append(("config set plugins '%s'" % text, replaced))
    for command, candidate in candidates:
        if not validate_config(candidate, repo, hints=False):
            return command
    return None


def write_config(repo: Any, config: Dict[str, Any]) -> Path:
    path = config_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(config, ensure_ascii=False, indent=2) + "\n"
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(str(temp), str(path))
    return path


def parse_value(text: str) -> Any:
    try:
        return json.loads(text)
    except ValueError:
        return text


def split_path(key_path: str) -> List[str]:
    """``键`` 或 ``键.子键``；只在第一个点处分开（2.8.0）：子键可以含点，例如 ``pricing.openai/gpt-4.1``。"""
    parts = key_path.split(".", 1)
    if any(not part for part in parts) or parts[0] not in KEYS:
        raise ConfigError("键路径必须是已知键，最多两层（例如 decisions.mode）：%r；已知键：%s" % (key_path, ", ".join(KEYS)), EXIT_USAGE)
    return parts


# ---------------------------------------------------------------------------
# 命令
# ---------------------------------------------------------------------------

def _effective(config: Dict[str, Any], repo: Any) -> List[Dict[str, Any]]:
    rows = []
    for key, (desc, default, _check) in KEYS.items():
        if key in config:
            value, source = config[key], "config"
        elif key == "worktree_root" and os.environ.get("PI_DISPATCH_WORKTREE_ROOT"):
            value, source = os.environ["PI_DISPATCH_WORKTREE_ROOT"], "env:PI_DISPATCH_WORKTREE_ROOT"
        else:
            value, source = None, "default"
        rows.append({"key": key, "value": value, "source": source, "default": default, "description": desc})
    return rows


def cmd_show(args: argparse.Namespace) -> int:
    repo = _repo(args.repo)
    config = load_config(repo)
    errors = validate_config(config, repo)
    rows = _effective(config, repo)
    facts: Dict[str, Any] = {"config_path": str(config_path(repo)), "exists": config_path(repo).exists(),
                             "errors": errors, "keys": rows}
    try:
        settings = _decisions.settings_from_config(config, repo.agent_dir, pd.DECISIONS_PLUGIN_DIR)
        described = _decisions.describe(settings, pd.DECISIONS_PLUGIN_DIR)
        facts["decisions"] = {"mode": described["mode"], "configured_mode": described["configured_mode"],
                              "reason": described["reason"], "marker_present": described["marker_present"],
                              "model": described["model"], "base_url": described["base_url"],
                              "points": described["points"], "env_var_name": settings.api_key_env,
                              "battery_lock": described.get("battery_lock"),
                              "secret": _store.describe(settings.api_key_env)}
    except _decisions.DecisionError as exc:
        facts["decisions"] = {"error": exc.detail}
    if args.json:
        print(json.dumps(facts, ensure_ascii=False, indent=2))
        return EXIT_OK if not errors else EXIT_FAIL
    print("配置文件：%s%s" % (facts["config_path"], "" if facts["exists"] else "（不存在，全部缺省）"))
    for row in rows:
        shown = json.dumps(row["value"], ensure_ascii=False) if row["source"] != "default" else "缺省（%s）" % row["default"]
        print("  %-24s %s  [%s]" % (row["key"], shown, row["source"]))
        print("  %-24s   %s" % ("", row["description"]))
    decisions = facts["decisions"]
    if "error" in decisions:
        print("决策模型：配置无效——%s" % decisions["error"])
    else:
        secret = decisions["secret"]
        print("决策模型：生效 %s（配置 %s，原因 %s）· 模型 %s · 标记文件 %s" % (
            decisions["mode"], decisions["configured_mode"], decisions["reason"], decisions["model"],
            "存在" if decisions["marker_present"] else "无"))
        print("  凭据 %s：%s（凭据库模式 %s，系统后端 %s）" % (
            decisions["env_var_name"], {"env": "环境变量已设置", "credential_store": "在系统凭据库里",
                                        "file": "在 0600 文件里", "none": "没有"}[secret["source"]],
            secret["store_mode"], secret["system_backend"] or "无"))
    for error in errors:
        print("ERROR %s" % error)
    return EXIT_OK if not errors else EXIT_FAIL


def cmd_validate(args: argparse.Namespace) -> int:
    repo = _repo(args.repo)
    errors = validate_config(load_config(repo), repo)
    for error in errors:
        print("ERROR %s" % error)
    print("配置%s：%s" % ("有效" if not errors else "无效（%d 个错误）" % len(errors), config_path(repo)))
    return EXIT_OK if not errors else EXIT_FAIL


def write_checked(repo: Any, config: Dict[str, Any]) -> None:
    """整份校验后原子写入；有错一个字节都不写（3.0 第一轮起公开，kit_plugins 用它写 plugins 段）。"""
    errors = validate_config(config, repo)
    if errors:
        raise ConfigError("没有写入：" + "；".join(errors))
    write_config(repo, config)


_write_checked = write_checked  # 旧名保留


def cmd_set(args: argparse.Namespace) -> int:
    repo = _repo(args.repo)
    parts = split_path(args.key)
    config = load_config(repo)
    value = parse_value(args.value)
    if len(parts) == 1:
        config[parts[0]] = value
    else:
        section = config.get(parts[0])
        if section is None:
            section = config[parts[0]] = {}
        if not isinstance(section, dict):
            raise ConfigError("%s 不是对象，不能设置 %s" % (parts[0], args.key))
        section[parts[1]] = value
    _write_checked(repo, config)
    print("已写入 %s：%s = %s" % (config_path(repo), args.key, json.dumps(value, ensure_ascii=False)))
    return EXIT_OK


def cmd_unset(args: argparse.Namespace) -> int:
    repo = _repo(args.repo)
    parts = split_path(args.key)
    config = load_config(repo)
    if len(parts) == 1:
        if parts[0] not in config:
            raise ConfigError("%s 本来就没有设置" % args.key)
        del config[parts[0]]
    else:
        section = config.get(parts[0])
        if not isinstance(section, dict) or parts[1] not in section:
            raise ConfigError("%s 本来就没有设置" % args.key)
        del section[parts[1]]
        if not section:
            del config[parts[0]]
    _write_checked(repo, config)
    print("已删除 %s（%s）" % (args.key, config_path(repo)))
    return EXIT_OK


def cmd_init(args: argparse.Namespace) -> int:
    repo = _repo(args.repo)
    target = config_path(repo)
    if target.exists():
        raise ConfigError("已存在：%s（用 set 修改，或先删除它）" % target)
    example = pd.KIT_ROOT / ".agent" / EXAMPLE_NAME
    if not example.is_file():
        raise ConfigError("kit 里没有 %s" % example)
    config = json.loads(example.read_text(encoding="utf-8"))
    errors = validate_config(config, repo)
    if errors:
        raise ConfigError("示例配置在本仓库上无效：" + "；".join(errors))
    write_config(repo, config)
    print("已生成 %s（来自 kit 的 %s）；用 show 查看、set 修改" % (target, EXAMPLE_NAME))
    return EXIT_OK


def cmd_decisions(args: argparse.Namespace) -> int:
    repo = _repo(args.repo)
    if args.what == "marker":
        marker = repo.agent_dir / _decisions.OFF_MARKER
        if args.state == "on":
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text("decisions are off while this file exists\n", encoding="utf-8")
            print("已创建 %s：决策功能一票否决为 off" % marker)
        else:
            if marker.exists():
                marker.unlink()
                print("已删除 %s：决策功能按配置生效" % marker)
            else:
                print("%s 本来就不存在" % marker)
        return EXIT_OK
    config = load_config(repo)
    section = config.get("decisions")
    if section is None:
        section = config["decisions"] = {}
    if not isinstance(section, dict):
        raise ConfigError("decisions 不是对象")
    section["mode"] = args.what
    _write_checked(repo, config)
    settings = _decisions.settings_from_config(config, repo.agent_dir, pd.DECISIONS_PLUGIN_DIR)
    print("已写入 decisions.mode = %s；实际生效 %s（%s）" % (args.what, settings.mode, settings.reason))
    return EXIT_OK


# ---------------------------------------------------------------------------
# 凭据：一次性本机网页与隐藏输入
# ---------------------------------------------------------------------------

_PAGE = """<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Code-Kit 凭据</title>
<meta name="referrer" content="no-referrer">
<style>
:root{color-scheme:light dark;--bg:#f6f5f1;--fg:#17181a;--mut:#5d6067;--card:#fff;--line:#d9d7d0;--acc:#1d5fd1;--on:#fff;--ok:#19794a;--bad:#b3261e}
@media(prefers-color-scheme:dark){:root{--bg:#121315;--fg:#ecebe7;--mut:#a2a5ac;--card:#1b1d20;--line:#2e3136;--acc:#7aa7ff;--on:#0b1220;--ok:#5fd39a;--bad:#ff8a80}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,-apple-system,Segoe UI,sans-serif;display:grid;place-items:center;min-height:100vh;padding:16px}
main{width:100%;max-width:460px;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:28px}
h1{font-size:1.3rem;margin:0 0 6px}p{margin:0 0 14px;color:var(--mut)}code{font-size:.95em}
label{display:block;font-weight:600;margin:18px 0 6px}
input{width:100%;padding:12px;border-radius:9px;border:1px solid var(--line);background:var(--bg);color:var(--fg);font:inherit}
button{margin-top:16px;width:100%;padding:12px;border:0;border-radius:9px;background:var(--acc);color:var(--on);font:600 1rem system-ui;cursor:pointer}
.note{font-size:.86rem;margin-top:18px}.ok{color:var(--ok)}.bad{color:var(--bad)}
</style></head><body><main>__BODY__</main></body></html>"""

_FORM = """<h1>存入凭据 <code>__NAME__</code></h1>
<p>把值粘贴到下面。它从这个页面直接进入这台电脑的凭据库（__WHERE__）；运行这条命令的 AI 代理看不到它。</p>
__ERROR__
<form method="post" autocomplete="off">
<label for="k">__NAME__ 的值</label>
<input id="k" name="value" type="password" required autofocus autocomplete="off" spellcheck="false">
<button type="submit">保存</button></form>
<p class="note">这一页只能用一次，十分钟后关闭；不要把值粘贴到对话里。</p>"""

_DONE = """<h1 class="ok">已保存</h1><p>凭据 <code>__NAME__</code> 已存入 __WHERE__。可以关闭这一页。</p>"""


def _render(body: str) -> bytes:
    return _PAGE.replace("__BODY__", body).encode("utf-8")


def run_page(name: str, *, host: str = "127.0.0.1", port: int = 0, timeout: float = PAGE_TIMEOUT,
             open_browser: bool = True, announce: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
    """一次性本机网页：随机令牌路径、拒绝外来 Host、只接受一次 POST、到时关闭。返回 {"stored", "backend"|"error"}。"""
    token = _secrets.token_urlsafe(24)
    where = (_store.system_backend().name if _store.store_mode() == "system" and _store.system_backend() else "file")
    state: Dict[str, Any] = {"stored": False, "backend": None, "error": None}
    done = threading.Event()

    def form(error: str = "") -> bytes:
        message = '<p class="bad">%s</p>' % html.escape(error) if error else ""
        return _render(_FORM.replace("__NAME__", html.escape(name)).replace("__WHERE__", html.escape(where))
                       .replace("__ERROR__", message))

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args: Any) -> None:  # 不记请求行，不记正文
            pass

        def _send(self, status: int, body: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(body)

        def _allowed(self) -> bool:
            if self.path.split("?", 1)[0] != "/" + token:
                return False
            host_header = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]")
            return host_header in ("127.0.0.1", "localhost", "::1")

        def do_GET(self) -> None:  # noqa: N802
            if not self._allowed():
                self._send(404, _render("<h1>404</h1>"))
                return
            self._send(200, form())

        def do_POST(self) -> None:  # noqa: N802
            if not self._allowed():
                self._send(404, _render("<h1>404</h1>"))
                return
            if done.is_set():
                self._send(410, _render("<h1 class='bad'>这一页已经用过了</h1>"))
                return
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                self._send(413, form("内容过长"))
                return
            raw = self.rfile.read(length).decode("utf-8", "replace")
            value = (parse_qs(raw).get("value") or [""])[0]
            if not _store.looks_like_secret(value):
                self._send(400, form("看起来不像凭据：8 到 %d 个可打印字符，不含空白" % _store.MAX_SECRET_CHARS))
                return
            try:
                state["backend"] = _store.store(name, value)
            except _store.SecretError as exc:
                state["error"] = exc.code
                self._send(500, form("没有存进去：%s" % exc.detail))
                done.set()
                return
            state["stored"] = True
            done.set()
            self._send(200, _render(_DONE.replace("__NAME__", html.escape(name)).replace("__WHERE__", html.escape(where))))

    server = ThreadingHTTPServer((host, port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = "http://%s:%d/%s" % (host, server.server_address[1], token)
    if announce:
        announce(url)
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:  # noqa: BLE001 - a headless box; the url was announced
            pass
    finished = done.wait(timeout)
    server.shutdown()
    server.server_close()
    if not finished:
        state["error"] = "timeout"
    return state


def cmd_secret(args: argparse.Namespace) -> int:
    name = args.name
    try:
        _store._check_name(name)
    except _store.SecretError as exc:
        raise ConfigError(exc.detail, EXIT_USAGE)
    if args.action == "check":
        print(json.dumps(_store.describe(name), ensure_ascii=False))
        return EXIT_OK
    if args.action == "remove":
        removed = _store.remove(name)
        print(json.dumps({"name": name, "removed_from": removed}, ensure_ascii=False))
        return EXIT_OK
    if _store.store_mode() == "off":
        raise ConfigError("%s=off：现在什么也存不了" % _store.STORE_ENV)
    if args.tty:
        if not sys.stdin.isatty():
            raise ConfigError("--tty 需要一个终端；在 AI 代理的会话里用网页方式（去掉 --tty）", EXIT_USAGE)
        value = getpass.getpass("%s 的值（不回显）：" % name)
        try:
            backend = _store.store(name, value)
        except _store.SecretError as exc:
            raise ConfigError("没有存进去：%s" % exc.detail)
        result: Dict[str, Any] = {"name": name, "stored": True, "backend": backend}
    else:
        state = run_page(name, timeout=args.timeout, open_browser=not args.no_browser,
                         announce=lambda url: print(json.dumps({"url": url, "note": "在这台电脑的浏览器里打开，粘贴后保存；只能用一次"},
                                                              ensure_ascii=False), file=sys.stderr, flush=True))
        result = {"name": name, "stored": state["stored"], "backend": state["backend"]}
        if state["error"]:
            result["error"] = state["error"]
    if result["stored"] and args.verify:
        repo = _repo(args.repo)
        settings = _decisions.settings_from_config(load_config(repo), repo.agent_dir, pd.DECISIONS_PLUGIN_DIR)
        if settings.api_key_env != name:
            result["verified"] = None
            result["verify_note"] = "decisions.api_key_env 是 %s，不是 %s；没有探测" % (settings.api_key_env, name)
        else:
            probe = _decisions.probe(settings)
            result["verified"] = probe["ok"]
            if not probe["ok"]:
                result["verify_error"] = probe["reason"]
    else:
        result["verified"] = None
    print(json.dumps(result, ensure_ascii=False))
    return EXIT_OK if result["stored"] else EXIT_FAIL


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kit_config.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", help="仓库路径（默认当前目录）")
    parser.add_argument("--version", action="version", version="kit_config %s" % TOOL_VERSION)
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("show", help="每个键的生效值与来源、决策模式、凭据来源")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("validate", help="整份校验，有错退出 1")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("set", help="设置一个键（先 JSON 解析，解析不了按字符串）")
    p.add_argument("key", help="键路径，最多两层，例如 decisions.mode")
    p.add_argument("value")
    p.set_defaults(func=cmd_set)

    p = sub.add_parser("unset", help="删除一个键")
    p.add_argument("key")
    p.set_defaults(func=cmd_unset)

    p = sub.add_parser("init", help="从 kit 的示例生成配置文件（已存在则拒绝）")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("decisions", help="决策模式：off | shadow | on，或 marker on|off")
    p.add_argument("what", choices=("off", "shadow", "on", "marker"))
    p.add_argument("state", nargs="?", choices=("on", "off"), help="marker 的开关")
    p.set_defaults(func=cmd_decisions)

    p = sub.add_parser("secret", help="凭据：set（网页或 --tty）、check、remove；从不打印值")
    p.add_argument("action", choices=("set", "check", "remove"))
    p.add_argument("name", help="环境变量名，例如 TYPESAFE_API_KEY")
    p.add_argument("--tty", action="store_true", help="在终端隐藏输入，不开网页")
    p.add_argument("--no-browser", action="store_true", help="不自动打开浏览器，只打印网址")
    p.add_argument("--timeout", type=float, default=PAGE_TIMEOUT, help="网页等待秒数（默认 600）")
    p.add_argument("--verify", action="store_true", help="存完向决策模型发一次最小请求（会联网、会花钱）")
    p.set_defaults(func=cmd_secret)
    return parser


def main(argv: Optional[Sequence[str]] = None, repo: Optional[str] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    if repo is not None and not args.repo:
        args.repo = repo
    if not getattr(args, "func", None):
        parser.print_help()
        return EXIT_USAGE
    if args.command == "decisions" and (args.what == "marker") != (args.state is not None):
        parser.error("decisions marker 需要 on 或 off；其它模式不带第二个参数")
    try:
        return int(args.func(args))
    except ConfigError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return exc.code
    except KeyboardInterrupt:
        print("已取消。", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
