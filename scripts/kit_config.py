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
import contextlib
import getpass
import hashlib
import html
import json
import os
import re
import secrets as _secrets
import shutil
import socket
import sys
import threading
import time
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
    """决策插件问题清单读之前的链接检查：第一个链接或 junction 的那一级，没有则 None。

    配置校验、写入门禁与修复提示的模拟都先过这一关（3.0 第一轮闸二 B1）。实现挪到了 pd.battery_link_problem：
    调度器运行时加载题库、doctor 与 config show 的展示也要先查，只保留一份实现。
    """
    return pd.battery_link_problem()


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
        raw = path.read_bytes()
    except OSError as exc:
        raise ConfigError("无法解析 %s：%s" % (path, exc))
    return _parse_object(path, raw)


def _parse_object(path: Path, raw: bytes) -> Dict[str, Any]:
    """配置文件的字节 → 顶层对象；解析不了或顶层不是对象都是 ConfigError。"""
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:  # RecursionError：嵌套过深的 JSON
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


def _installed_plugin_ids() -> Optional[List[str]]:
    """当前布局下 KIT_ROOT/plugins/ 里的插件目录名（匹配插件 ID、不是链接），按名字排序。

    plugins/ 根是目录却列不出来时 None（闸二第 2 轮 B2）：调用方不能把它当作“没有插件”。
    """
    root = pd.KIT_ROOT / "plugins"
    try:
        if pd.is_link_or_junction(root) or not root.is_dir():
            return []
        return sorted(entry.name for entry in root.iterdir()
                      if _plugins.PLUGIN_ID.fullmatch(entry.name) and entry.is_dir()
                      and not pd.is_link_or_junction(entry))
    except OSError:
        return None


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
    if base is None:  # plugins/ 根列不出来：不给“换成显式列表”的提示，它会把全部插件关掉
        for command, candidate in candidates:
            if not validate_config(candidate, repo, hints=False):
                return command
        return None
    replacement["enabled"] = [name for name in base if name != _decisions.PLUGIN_ID]
    replaced = json.loads(json.dumps(config))
    replaced["plugins"] = replacement
    # 单引号写成 JSON 的 \u0027 转义：整段放进单引号，bash 与 PowerShell 都能原样执行（闸二 S1）
    # 闸二第 2 轮 S1：非 ASCII 字符（含 PowerShell 也当作单引号的弯引号 U+2018–U+201B）一并写成 JSON 转义
    text = json.dumps(replacement, ensure_ascii=True, separators=(",", ":")).replace("'", "\\u0027")
    candidates.append(("config set plugins '%s'" % text, replaced))
    for command, candidate in candidates:
        if not validate_config(candidate, repo, hints=False):
            return command
    return None


# ---------------------------------------------------------------------------
# 配置锁、写入事务、历史与审计（3.0 第二轮设计 D7）
# ---------------------------------------------------------------------------

LOCK_NAME = ".config.lock"
#: 等配置锁的秒数。测试把它改小：锁从不自动清除，泄漏的锁会让之后的每次写入都等满这么久。
LOCK_WAIT_SECONDS = 30.0
HISTORY_DIR = "config-history"
AUDIT_DIR = "audit"
AUDIT_NAME = "management.jsonl"
LOCAL_NAME = "dispatch.local.json"
ACTOR_ENV = "CODEKIT_ACTOR"
ACTOR_RE = re.compile(r"^(?:user|agent:[a-z][a-z_]{0,31})$")
#: 审计记录的 resource → .agent/ 下的文件。补判、外部改动都只在同一资源内比较；只有 config 存快照。
RESOURCES = {"config": CONFIG_NAME, "local": LOCAL_NAME}
APPROVAL_NOTE = "P3 之前没有批准记录"


class AuditIncomplete(ConfigError):
    """配置已经替换，但 commit 记录没有写进审计：退出 1；下一次写入同一资源时补判（D7 第 8 步）。"""


class ConfigLock:
    """配置锁 .agent/.config.lock/：mkdir 成功就持有，owner.json 记 pid、主机、令牌与创建时间。

    从不自动抢占（闸一第 3 轮 B1）：被占用时等 LOCK_WAIT_SECONDS 秒，之后报错并写明持有者是否还在运行，
    由人确认后删除。释放时令牌一致才删除目录。不复用 pi_dispatch.TaskLock：它按年龄清锁、退出时不核对所有权，
    会让被挂起的旧持有者恢复后接着写。替换用的临时文件也放在锁目录里，锁释放时一并删掉。
    """

    def __init__(self, repo: Any, wait_seconds: Optional[float] = None) -> None:
        self.path = repo.agent_dir / LOCK_NAME
        self.wait_seconds = LOCK_WAIT_SECONDS if wait_seconds is None else wait_seconds
        self.token = _secrets.token_hex(16)

    def __enter__(self) -> "ConfigLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.wait_seconds
        while True:
            try:
                self.path.mkdir()
                break
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise ConfigError(self._busy_message())
                time.sleep(0.1)
        owner = {"pid": os.getpid(), "host": socket.gethostname(), "token": self.token, "created_at": pd.utc_now()}
        try:
            (self.path / "owner.json").write_text(json.dumps(owner) + "\n", encoding="utf-8")
        except OSError as exc:
            shutil.rmtree(str(self.path), ignore_errors=True)
            raise ConfigError("写不进配置锁 %s：%s" % (self.path, exc))
        return self

    def __exit__(self, *_exc: Any) -> None:
        owner = _read_owner(self.path)
        if owner is not None and owner.get("token") == self.token:  # 令牌不同：锁已被人删掉又被别人重建，不动它
            shutil.rmtree(str(self.path), ignore_errors=True)

    def _busy_message(self) -> str:
        owner = _read_owner(self.path)
        if owner is None:
            who = "持有者信息读不出来"
        else:
            pid = owner.get("pid") if isinstance(owner.get("pid"), int) else None
            host = owner.get("host")
            if host == socket.gethostname():
                state = {True: "仍在运行", False: "已退出", None: "无法判断是否在运行"}[pd.pid_alive(pid)]
            else:
                state = "在另一台主机上，无法判断是否在运行"
            who = "进程 %s（主机 %s，%s，%s 起持有）" % (pid, host, state, owner.get("created_at"))
        return ("配置锁被占用：%s，%s。确认没有别的写配置的命令在运行之后，删除这个目录再重试（锁从不自动清除）"
                % (self.path, who))


def _read_owner(lock_dir: Path) -> Optional[Dict[str, Any]]:
    try:
        owner = json.loads((lock_dir / "owner.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return owner if isinstance(owner, dict) else None


def _sha(data: Optional[bytes]) -> Optional[str]:
    return hashlib.sha256(data).hexdigest() if data is not None else None


def _actor() -> str:
    """CODEKIT_ACTOR 的自声明（user 或 agent:<角色>），没设记 undeclared。这不是认证（上位设计 8.6）。"""
    value = os.environ.get(ACTOR_ENV)
    if not value:
        return "undeclared"
    if ACTOR_RE.match(value):
        return value
    print("WARN  %s=%r 不是 user 或 agent:<角色>，审计记为 undeclared" % (ACTOR_ENV, value), file=sys.stderr)
    return "undeclared"


def audit_path(repo: Any) -> Path:
    return repo.agent_dir / AUDIT_DIR / AUDIT_NAME


def read_audit(repo: Any) -> Tuple[List[Dict[str, Any]], List[int]]:
    """审计记录（文件顺序，每条带 _line）与损坏行的行号。末尾的半行、解析不了的行都记为损坏，不中断。"""
    try:
        data = audit_path(repo).read_bytes()
    except FileNotFoundError:
        return [], []
    except OSError as exc:
        raise ConfigError("读不出审计 %s：%s" % (audit_path(repo), exc))
    records: List[Dict[str, Any]] = []
    broken: List[int] = []
    for number, raw in enumerate(data.split(b"\n"), 1):
        if not raw.strip():
            continue
        try:
            record = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError, RecursionError):
            broken.append(number)
            continue
        if not isinstance(record, dict) or record.get("record_type") != "management-audit":
            broken.append(number)
            continue
        record["_line"] = number
        records.append(record)
    return records, broken


def _append_audit(repo: Any, record: Dict[str, Any]) -> None:
    """只在配置锁内调用：同一时间只有一个追加者。文件不以换行结尾时先补一个，中断留下的半行单独成行。"""
    path = audit_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    prefix = b""
    if path.exists():
        with open(path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            if handle.tell():
                handle.seek(-1, os.SEEK_END)
                prefix = b"" if handle.read(1) == b"\n" else b"\n"
    line = prefix + (json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    with open(path, "ab") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())


def _secret_reason(data: bytes) -> Optional[str]:
    """快照存内容之前的凭据检查（D7）：疑似凭据时返回原因（只含键路径，不含值），否则 None。"""
    try:
        parsed = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError):
        text = data.decode("utf-8", "replace")
        return "不是合法的 JSON，文本里有疑似凭据" if pd.redact_secrets(text) != text else None
    paths = pd.secret_like_paths(parsed)
    return ("疑似凭据：%s" % "、".join(paths[:5])) if paths else None


def _snapshot_ref(repo: Any, resource: str, data: Optional[bytes], *, store: bool) -> Optional[Dict[str, Any]]:
    """一份内容在审计里的引用；store 为真且是 config、没有疑似凭据时，按内容寻址存进 config-history/。"""
    if data is None:
        return None
    sha = _sha(data)
    if resource != "config":
        return {"kind": "local-file", "sha256": sha, "stored": False}
    target = repo.agent_dir / HISTORY_DIR / ("%s.json" % sha)
    if target.is_file():
        return {"kind": "config-snapshot", "sha256": sha, "stored": True}
    reason = _secret_reason(data)
    if reason is not None:
        return {"kind": "config-snapshot", "sha256": sha, "stored": False, "reason": reason}
    if not store:
        return {"kind": "config-snapshot", "sha256": sha, "stored": False}
    target.parent.mkdir(parents=True, exist_ok=True)
    pd.publish_new(target, data)  # 已存在（同一内容）返回 False，无妨
    return {"kind": "config-snapshot", "sha256": sha, "stored": True}


def _ledger(records: List[Dict[str, Any]], resource: str) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, str],
                                                                    List[str], Optional[str]]:
    """一个资源的账：intent（txn → 记录）、终结结果（txn → result）、未终结的 txn（日志顺序），
    以及按日志顺序最后一条“已知内容”的哈希——已发布事务的 after 或 observed 的 after（D7 第 3、4 步）。"""
    intents: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    terminal: Dict[str, str] = {}
    last_known: Optional[str] = None
    for record in records:
        if record.get("resource") != resource:
            continue
        phase, txn = record.get("phase"), record.get("txn")
        if phase == "intent" and isinstance(txn, str) and txn not in intents:
            intents[txn] = record
            order.append(txn)
        elif phase in ("commit", "resolve") and txn in intents and txn not in terminal:
            terminal[txn] = str(record.get("result"))
            if record.get("result") == "published":
                last_known = (intents[txn].get("after_ref") or {}).get("sha256")
        elif phase == "observed":
            last_known = (record.get("after_ref") or {}).get("sha256")
    return intents, terminal, [txn for txn in order if txn not in terminal], last_known


def _warn_unignored(repo: Any) -> None:
    """历史与审计目录没被忽略（旧安装没补规则）时提示：它们会作为未跟踪文件出现，运行期间写配置会进复审关注。"""
    for name in (HISTORY_DIR, AUDIT_DIR):
        probe = ".agent/%s/probe" % name
        if pd.git(["check-ignore", "-q", probe], repo.root, check=False).returncode != 0:
            print("WARN  .agent/%s/ 没有被 .gitignore 忽略：运行 kit_install update 补上 kit 的忽略规则" % name,
                  file=sys.stderr)


class ConfigTransaction:
    """一次写入：在配置锁内读入资源，调用方修改后 publish；不 publish 就什么也不写（D7）。"""

    def __init__(self, repo: Any, lock: ConfigLock, resource: str, action: str, target: Optional[str],
                 confirm: bool) -> None:
        self.repo, self.lock, self.resource = repo, lock, resource
        self.action, self.target, self.confirm = action, target, confirm
        self.path = repo.agent_dir / RESOURCES[resource]
        try:
            self.before: Optional[bytes] = self.path.read_bytes() if self.path.exists() else None
        except OSError as exc:
            raise ConfigError("读不出 %s：%s" % (self.path, exc))
        self.config: Dict[str, Any] = {} if self.before is None else _parse_object(self.path, self.before)
        self.published = False

    def _record(self, phase: str, **fields: Any) -> Dict[str, Any]:
        record = {"record_type": "management-audit", "schema_version": 1, "phase": phase,
                  "resource": self.resource, "audit_id": "aud-%s" % _secrets.token_hex(16), "at": pd.utc_now()}
        record.update(fields)
        return record

    def publish(self, new_config: Dict[str, Any], raw_text: Optional[str] = None) -> bool:
        """校验并写入；新字节与当前相同时什么也不写、返回 False。raw_text 给定时原样写这份字节（rollback 用）。

        顺序（D7）：校验 → 确认（D8）→ 补判本资源中断的事务 → 外部改动 → 快照 → intent → 替换 → commit。
        校验不过、需要确认而没有确认、没有变化时一条记录也不写。
        """
        data = (raw_text if raw_text is not None
                else json.dumps(new_config, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if self.before is not None and data == self.before:
            return False
        if self.resource == "config":
            errors = validate_config(new_config, self.repo)
            if errors:
                raise ConfigError("没有写入：" + "；".join(errors))
        confirmation = _binding_switch_confirmation(self.repo, self.config, new_config, self.confirm) \
            if self.resource == "config" else "none"
        records, _broken = read_audit(self.repo)
        intents, _terminal, pending, last_known = _ledger(records, self.resource)
        current = _sha(self.before)
        for txn in pending:  # 持锁者总会先写完自己的事务再放锁、锁又不自动清除，所以未终结的都是中断者留下的
            intent = intents[txn]
            after = (intent.get("after_ref") or {}).get("sha256")
            before = (intent.get("before_ref") or {}).get("sha256")
            result = "published" if current == after else ("aborted" if current == before else "unknown")
            self._append(self._record("resolve", txn=txn, result=result))
            if result == "published":
                last_known = after
        if current != last_known:
            self._append(self._record("observed", action="external",
                                      after_ref=self._snapshot(self.before, store=True)))
        after_ref = self._snapshot(data, store=True)
        before_ref = self._snapshot(self.before, store=False)
        txn = _secrets.token_hex(16)
        intent = self._record("intent", txn=txn, action=self.action, target=self.target, actor=_actor(),
                              confirmation=confirmation, before_ref=before_ref, after_ref=after_ref,
                              invalidated_approvals=[], note=APPROVAL_NOTE)
        try:
            _append_audit(self.repo, intent)
        except OSError as exc:
            raise ConfigError("没有写入：审计写不进去（%s）" % exc)
        temp = self.lock.path / ("%s.%s.tmp" % (self.path.name, _secrets.token_hex(8)))
        try:
            temp.write_bytes(data)
            os.replace(str(temp), str(self.path))
        except OSError as exc:
            raise ConfigError("写入失败：%s" % exc)
        try:
            _append_audit(self.repo, self._record("commit", txn=txn, result="published"))
        except OSError as exc:
            raise AuditIncomplete("已写入 %s，但审计记录不全（%s）：下一次写入时补判" % (self.path, exc))
        self.published = True
        _warn_unignored(self.repo)
        return True

    def _append(self, record: Dict[str, Any]) -> None:
        try:
            _append_audit(self.repo, record)
        except OSError as exc:
            raise ConfigError("没有写入：审计写不进去（%s）" % exc)

    def _snapshot(self, data: Optional[bytes], *, store: bool) -> Optional[Dict[str, Any]]:
        try:
            return _snapshot_ref(self.repo, self.resource, data, store=store)
        except OSError as exc:
            raise ConfigError("没有写入：快照存不下（%s）" % exc)


@contextlib.contextmanager
def config_transaction(repo: Any, action: str, target: Optional[str] = None, *, resource: str = "config",
                       confirm: bool = False):
    """持配置锁读入资源（config 或 local），交给调用方修改并 publish。所有写配置的入口都经过这里（D7）。"""
    with ConfigLock(repo) as lock:
        yield ConfigTransaction(repo, lock, resource, action, target, confirm)


def _binding_switch_confirmation(repo: Any, old_config: Dict[str, Any], new_config: Dict[str, Any],
                                 confirm: bool) -> str:
    """运行中切换的确认（D8）：返回审计的 confirmation（flag / none）。

    写入前后两份配置都没有 v3 键时，生效绑定两边都是“由合同决定”，不用比较；有 v3 键的比较在 kit_roles 里。
    """
    if not any(key in config for config in (old_config, new_config) for key in V3_KEYS):
        return "none"
    roles = _kit_roles()
    in_flight = roles.binding_switch_in_flight(repo, old_config, new_config)
    if not in_flight:
        return "none"
    if not confirm:
        raise ConfigError("有 attempt 在运行，这次写入会改变 execution 或 contract 的生效绑定：%s。"
                          "运行中的 attempt 不受影响（执行模型已固定）；确认要切换就加 --yes" % "、".join(in_flight))
    return "flag"


#: 配置 v3 的五个键（3.0 第二轮 D1）；第 2 步登记进 KEYS。
V3_KEYS: Tuple[str, ...] = ()


def _kit_roles() -> Any:
    """惰性导入 scripts/kit_roles.py：只有配置里有 v3 键时才需要它（D12）。"""
    try:
        import kit_roles  # noqa: PLC0415
    except ModuleNotFoundError:
        raise ConfigError("配置里有角色绑定的键，但 scripts/kit_roles.py 不在本工具旁边", EXIT_USAGE)
    return kit_roles


def write_config(repo: Any, config: Dict[str, Any]) -> Path:
    """经写入事务整份校验后写入（3.0 第二轮起没有绕过历史与审计的写法）；返回配置路径。"""
    with config_transaction(repo, "config.write") as txn:
        txn.publish(config)
    return config_path(repo)


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
        described = pd.describe_decisions(_decisions, settings)  # 问题清单经过链接时不读（battery_lock 记 link）
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


def write_checked(repo: Any, config: Dict[str, Any], *, action: str = "config.write", target: Optional[str] = None,
                  confirm: bool = False) -> bool:
    """整份校验后经写入事务写入，有错一个字节都不写；返回是否有变化（3.0 第一轮起公开）。

    调用方在锁外读出、改好再交进来，与锁内的读改写之间仍可能丢更新；本仓库的入口都改用 config_transaction。
    """
    with config_transaction(repo, action, target, confirm=confirm) as txn:
        return txn.publish(config)


_write_checked = write_checked  # 旧名保留


def _confirm_flag(args: argparse.Namespace) -> bool:
    return bool(getattr(args, "yes", False))


def cmd_set(args: argparse.Namespace) -> int:
    repo = _repo(args.repo)
    parts = split_path(args.key)
    value = parse_value(args.value)
    with config_transaction(repo, "config.set", args.key, confirm=_confirm_flag(args)) as txn:
        config = txn.config
        if len(parts) == 1:
            config[parts[0]] = value
        else:
            section = config.get(parts[0])
            if section is None:
                section = config[parts[0]] = {}
            if not isinstance(section, dict):
                raise ConfigError("%s 不是对象，不能设置 %s" % (parts[0], args.key))
            section[parts[1]] = value
        changed = txn.publish(config)
    print("%s %s：%s = %s" % ("已写入" if changed else "没有变化", config_path(repo), args.key,
                             json.dumps(value, ensure_ascii=False)))
    return EXIT_OK


def cmd_unset(args: argparse.Namespace) -> int:
    repo = _repo(args.repo)
    parts = split_path(args.key)
    with config_transaction(repo, "config.unset", args.key, confirm=_confirm_flag(args)) as txn:
        config = txn.config
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
        txn.publish(config)
    print("已删除 %s（%s）" % (args.key, config_path(repo)))
    return EXIT_OK


def cmd_init(args: argparse.Namespace) -> int:
    repo = _repo(args.repo)
    target = config_path(repo)
    example = pd.KIT_ROOT / ".agent" / EXAMPLE_NAME
    with config_transaction(repo, "config.init") as txn:
        if txn.before is not None:
            raise ConfigError("已存在：%s（用 set 修改，或先删除它）" % target)
        if not example.is_file():
            raise ConfigError("kit 里没有 %s" % example)
        config = json.loads(example.read_text(encoding="utf-8"))
        errors = validate_config(config, repo)
        if errors:
            raise ConfigError("示例配置在本仓库上无效：" + "；".join(errors))
        txn.publish(config)
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
    with config_transaction(repo, "config.decisions", "decisions.mode") as txn:
        config = txn.config
        section = config.get("decisions")
        if section is None:
            section = config["decisions"] = {}
        if not isinstance(section, dict):
            raise ConfigError("decisions 不是对象")
        section["mode"] = args.what
        txn.publish(config)
    settings = _decisions.settings_from_config(config, repo.agent_dir, pd.DECISIONS_PLUGIN_DIR)
    print("已写入 decisions.mode = %s；实际生效 %s（%s）" % (args.what, settings.mode, settings.reason))
    return EXIT_OK


# ---------------------------------------------------------------------------
# 历史与回滚（D7）
# ---------------------------------------------------------------------------

STATE_WORDS = {"published": "已发布", "aborted": "未发布", "unknown": "未知", None: "进行中或已中断"}


def history_entries(repo: Any) -> Tuple[List[Dict[str, Any]], List[int], int]:
    """按 intent 在日志中的顺序编号（两种资源共用一套编号），每条带终结状态；返回（条目, 损坏行, 第 1 条之前的
    外部改动次数）。observed 记录记在它前面那一条上：那条之后、下一次写入之前，有人在配置中心之外改过。

    只读：不持锁、不补判，没有终结记录的标“进行中或已中断”。
    """
    records, broken = read_audit(repo)
    entries: List[Dict[str, Any]] = []
    by_txn: Dict[Tuple[str, str], Dict[str, Any]] = {}
    leading_external = 0
    for record in records:
        phase, resource = record.get("phase"), record.get("resource")
        if phase == "intent" and isinstance(record.get("txn"), str):
            entry = {"number": len(entries) + 1, "resource": resource, "txn": record["txn"], "at": record.get("at"),
                     "action": record.get("action"), "target": record.get("target"), "actor": record.get("actor"),
                     "confirmation": record.get("confirmation"), "before_ref": record.get("before_ref"),
                     "after_ref": record.get("after_ref"), "state": None, "resolved": False, "external_after": 0}
            entries.append(entry)
            by_txn[(str(resource), record["txn"])] = entry
        elif phase in ("commit", "resolve"):
            entry = by_txn.get((str(resource), str(record.get("txn"))))
            if entry is not None and entry["state"] is None:
                entry["state"] = record.get("result")
                entry["resolved"] = phase == "resolve"
        elif phase == "observed":
            if entries:
                entries[-1]["external_after"] += 1
            else:
                leading_external += 1
    return entries, broken, leading_external


def _snapshot_bytes(repo: Any, ref: Optional[Dict[str, Any]]) -> Optional[bytes]:
    if not ref or not ref.get("stored") or not isinstance(ref.get("sha256"), str):
        return None
    path = repo.agent_dir / HISTORY_DIR / ("%s.json" % ref["sha256"])
    try:
        data = path.read_bytes()
    except OSError:
        return None
    return data if _sha(data) == ref["sha256"] else None


def _flatten(value: Any, prefix: str = "") -> Dict[str, Any]:
    """{键路径: 值}；非空对象逐级展开，空对象与其他值是叶子。顶层是空对象时没有任何键。"""
    if isinstance(value, dict) and (value or not prefix):
        flat: Dict[str, Any] = {}
        for key, item in value.items():
            flat.update(_flatten(item, "%s.%s" % (prefix, key) if prefix else str(key)))
        return flat
    return {prefix or "（顶层）": value}


def key_diff(before: Optional[bytes], after: Optional[bytes]) -> Optional[List[Tuple[str, Any, Any]]]:
    """逐键差异（键路径、旧值、新值）；任一份内容不可用时 None。缺省的一侧记 None。"""
    try:
        old = json.loads(before.decode("utf-8")) if before is not None else {}
        new = json.loads(after.decode("utf-8")) if after is not None else {}
    except (AttributeError, UnicodeDecodeError, ValueError, RecursionError):
        return None
    old_flat, new_flat = _flatten(old), _flatten(new)
    return [(key, old_flat.get(key), new_flat.get(key)) for key in sorted(set(old_flat) | set(new_flat))
            if old_flat.get(key, KeyError) != new_flat.get(key, KeyError)]


def _content_note(resource: Any, ref: Optional[Dict[str, Any]]) -> Optional[str]:
    if ref is None or ref.get("stored"):
        return None
    return "本机配置只存哈希" if resource == "local" else "疑似凭据，未存内容"


def cmd_history(args: argparse.Namespace) -> int:
    repo = _repo(args.repo)
    entries, broken, leading_external = history_entries(repo)
    if getattr(args, "number", None) is not None:
        return _history_show(repo, entries, args.number, args.json)
    rows = []
    for entry in entries:
        before = _snapshot_bytes(repo, entry["before_ref"]) if entry["before_ref"] else b"{}"
        after = _snapshot_bytes(repo, entry["after_ref"])
        diff = key_diff(before, after) if entry["resource"] == "config" else None
        rows.append({"number": entry["number"], "resource": entry["resource"], "at": entry["at"],
                     "action": entry["action"], "target": entry["target"], "actor": entry["actor"],
                     "confirmation": entry["confirmation"], "state": entry["state"], "resolved": entry["resolved"],
                     "changed_keys": [item[0] for item in diff] if diff is not None else None,
                     "note": _content_note(entry["resource"], entry["after_ref"]),
                     "external_changes": entry["external_after"]})
    if args.json:
        print(json.dumps({"entries": rows, "broken_lines": broken, "external_before_first": leading_external},
                         ensure_ascii=False, indent=2))
        return EXIT_OK
    if not rows:
        print("还没有写入记录：%s" % audit_path(repo))
    if leading_external:
        print("第 1 条之前：配置中心之外已有的内容（记为基线，observed %d 次）" % leading_external)
    for row in rows:
        state = STATE_WORDS.get(row["state"], str(row["state"])) + ("（补判）" if row["resolved"] else "")
        keys = "、".join(row["changed_keys"]) if row["changed_keys"] else (row["note"] or "—")
        print("%4d  %s  %-6s %-18s %-24s %s · %s · 确认 %s  [%s]" % (
            row["number"], row["at"], row["resource"], row["action"], row["target"] or "—", state, row["actor"],
            row["confirmation"], keys))
        if row["external_changes"]:
            print("      之后发现 %d 次在配置中心之外的改动（observed）" % row["external_changes"])
    if broken:
        print("损坏的记录：第 %s 行" % "、".join(str(number) for number in broken))
    return EXIT_OK


def _entry(entries: List[Dict[str, Any]], number: int) -> Dict[str, Any]:
    for entry in entries:
        if entry["number"] == number:
            return entry
    raise ConfigError("没有第 %d 条写入记录（用 config history 查看编号）" % number, EXIT_USAGE)


def _history_show(repo: Any, entries: List[Dict[str, Any]], number: int, as_json: bool) -> int:
    entry = _entry(entries, number)
    if entry["resource"] != "config":
        facts = {"number": number, "resource": entry["resource"], "state": entry["state"],
                 "before_sha256": (entry["before_ref"] or {}).get("sha256"),
                 "after_sha256": (entry["after_ref"] or {}).get("sha256"), "note": "本机配置只存哈希"}
        print(json.dumps(facts, ensure_ascii=False, indent=2) if as_json else
              "第 %d 条（%s）：%s → %s；本机配置只存哈希，没有逐键差异" % (
                  number, entry["resource"], facts["before_sha256"], facts["after_sha256"]))
        return EXIT_OK
    before = _snapshot_bytes(repo, entry["before_ref"]) if entry["before_ref"] else b"{}"
    after = _snapshot_bytes(repo, entry["after_ref"])
    diff = key_diff(before, after)
    note = None
    if diff is None:
        note = _content_note("config", entry["after_ref"] if after is None else entry["before_ref"]) or "快照缺失"
    if as_json:
        print(json.dumps({"number": number, "state": entry["state"], "note": note,
                          "diff": None if diff is None else [{"key": k, "old": o, "new": n} for k, o, n in diff]},
                         ensure_ascii=False, indent=2))
        return EXIT_OK
    if diff is None:
        print("第 %d 条：%s，没有逐键差异" % (number, note))
        return EXIT_OK
    print("第 %d 条：%s %s（%s）" % (number, entry["action"], entry["target"] or "", STATE_WORDS.get(entry["state"])))
    for key, old, new in diff:
        print("  %s: %s → %s" % (key, "未设置" if old is None else json.dumps(old, ensure_ascii=False),
                                  "未设置" if new is None else json.dumps(new, ensure_ascii=False)))
    return EXIT_OK


def cmd_rollback(args: argparse.Namespace) -> int:
    """回到某条已发布写入之后的配置：原样写回那份快照的字节，本身也是一个新的事务（action config.rollback）。"""
    repo = _repo(args.repo)
    with config_transaction(repo, "config.rollback", str(args.number), confirm=_confirm_flag(args)) as txn:
        entries, _broken, _leading = history_entries(repo)
        entry = _entry(entries, args.number)
        if entry["resource"] != "config":
            raise ConfigError("第 %d 条是本机文件的写入：rollback 只接受配置文件的记录" % args.number, EXIT_USAGE)
        if entry["state"] != "published":
            raise ConfigError("第 %d 条没有发布（%s），不能回滚到它" % (
                args.number, STATE_WORDS.get(entry["state"], entry["state"])), EXIT_USAGE)
        data = _snapshot_bytes(repo, entry["after_ref"])
        if data is None:
            raise ConfigError("第 %d 条的快照没有存内容或已缺失（%s），不能回滚" % (
                args.number, _content_note("config", entry["after_ref"]) or "快照文件缺失"))
        target = _parse_object(repo.agent_dir / HISTORY_DIR / ("%s.json" % entry["after_ref"]["sha256"]), data)
        changed = txn.publish(target, raw_text=data.decode("utf-8"))
    print("%s：%s 回到第 %d 条之后的内容" % ("已回滚" if changed else "没有变化", config_path(repo), args.number))
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
    p.add_argument("--yes", action="store_true", help="有 attempt 在运行时，确认要改变执行端或合同端的生效绑定")
    p.set_defaults(func=cmd_set)

    p = sub.add_parser("unset", help="删除一个键")
    p.add_argument("key")
    p.add_argument("--yes", action="store_true", help="有 attempt 在运行时，确认要改变执行端或合同端的生效绑定")
    p.set_defaults(func=cmd_unset)

    p = sub.add_parser("history", help="写入历史：编号、动作、执行者、变化的键；history show <编号> 看逐键差异")
    p.add_argument("show", nargs="?", choices=("show",))
    p.add_argument("number", nargs="?", type=int)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_history)

    p = sub.add_parser("rollback", help="回到第 N 条已发布写入之后的配置（原样写回快照的字节，本身也记一条历史）")
    p.add_argument("number", type=int)
    p.add_argument("--yes", action="store_true", help="有 attempt 在运行时，确认要改变执行端或合同端的生效绑定")
    p.set_defaults(func=cmd_rollback)

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
    if args.command == "history" and (args.show is None) != (args.number is None):
        parser.error("history show 需要编号；只看列表时不带参数")
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
