#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""旧行为特征化回归（01-A07、01 文档 C.4）的测试工具。

用途：锁定 HEAD（a4fa199）时旧调度器 scripts/pi_dispatch.py 的**现有**行为（不是修 bug）。后续的特征化测试
都从这里取临时仓库、受控环境、假 pi 与断言辅助函数。本文件不是测试（文件名不匹配 test_*.py），导入时只解析
路径与常量：不建目录、不起进程、不读被测源码、不写任何东西（01-L04）。

为什么不导入 tests/test_dispatch.py：它在导入时就在系统临时目录建目录（:24），并继承宿主的全部环境变量
（:28-32）。这里把需要的辅助逻辑重写，每个函数的 docstring 注明对应的原函数与行号（tests/test_dispatch.py，
提交 a4fa199）。

被测源码目录 KIT
----------------
默认是本仓库根目录；设置环境变量 CODEKIT_LEGACY_KIT_DIR 时改用它（供复审者在临时副本里对 pi_dispatch.py 做
变异反测）。KIT 下必须有 scripts/pi_dispatch.py 与 scripts/dispatch-pi.sh，否则报错（不静默退回）。
临时仓库按 test_dispatch 的方式从 KIT 复制这两个脚本；stub 取 KIT/tests/stub_pi.py，KIT 中没有时退回本文件
所在目录的 stub_pi.py（legacy_facts()["stub_from_kit"] 会如实记录）。legacy_source_digest() 返回
KIT/scripts/pi_dispatch.py 的 sha256，测试报告里用；legacy_facts() 给出完整的来源记录，其中
pi_dispatch_matches_a4fa199 按 CRLF 归一为 LF 后的摘要判定（本机 core.autocrlf=true 检出的 CRLF 副本也算匹配）。

环境隔离（01-L05，由本工具自己保证，不依赖调用者的 shell）
-------------------------------------------------------
子进程环境从 os.environ 复制后（只按变量名判断，不读取、不输出变量值）：
- 删除：PI_EXEC_*、STUB_*、PI_DISPATCH_*（随后重设 PI_CMD）、GIT_CONFIG*（随后重设 GLOBAL）、Git 仓库重定向变量
  （GIT_DIR 等）、GIT_COMMITTER_*（GIT_AUTHOR_* 已被下一条删除）、PYTHONPATH/PYTHONSTARTUP/PYTHONIOENCODING/
  PYTHONUTF8/PYTHONWARNINGS，以及名字匹配 ``(?i)(token|secret|password|credential|api_?key|auth)`` 的变量；
- PATH：去掉空条目、相对条目，以及任何含 pi/claude/codex 可执行文件（无扩展名与 .exe/.cmd/.bat/.ps1/.com，
  以及 PATHEXT 中的扩展名）的目录；隔离后 PATH 中必须仍能找到 git，否则报错；
- 设置：PI_DISPATCH_PI_CMD=[sys.executable, <stub_pi.py>]；PI_CODING_AGENT_DIR=每个用例自建的空目录；
  GIT_CONFIG_GLOBAL=每个用例自建的空文件（不读宿主的用户级 Git 配置；系统级配置照常生效，本机为
  core.autocrlf=true）；PYTHONDONTWRITEBYTECODE=1；GIT_TERMINAL_PROMPT=0；GCM_INTERACTIVE=never。
每次起子进程前都用 assert_isolated() 复核；测试通过 env= 显式传入的变量（例如 STUB_SCENARIO、STUB_AUTH）
在删除规则之后生效，属于测试的输入。测试若显式改 PATH 或 PI_DISPATCH_PI_CMD，其中出现的 pi/claude/codex
只能位于本用例的临时区域内，否则拒绝运行（IsolationError）。

与 test_dispatch 的差异（均为隔离或防挂起所需，不改变被测脚本的输入）
------------------------------------------------------------------
- 每个用例一个临时区域 make_temp_area()：tempfile.mkdtemp(prefix="codekit-legacy-")，取真实路径（Windows 的
  TEMP 常是 8.3 短名形式，调度器记录的路径是长名），并在根目录写入所有权标记 .codekit-legacy-owner（随机值，
  期望值只记在本进程内存中）；用 addCleanup 清理：先结束登记过的进程，再 git worktree prune，最后删除（只读
  文件先改权限；Windows 上短暂重试），删除失败会作为用例错误报告，不吞掉。
- 清理前核对归属（01 文档 8.4）：remove_tree 只删除本进程 make_temp_area() 建立的区域本身或其中的路径，且要求
  区域的真实路径是 realpath(tempfile.gettempdir()) 的直接子目录（按路径分段比较，不做大小写折叠）、目录名以
  codekit-legacy- 开头、目录身份未变、标记内容与本进程记录的随机值一致；任一项不成立时抛 CleanupOwnershipError、
  不删除（测试报错而不是误删）。原函数不做这些核对。
- 子进程 stdin 为 DEVNULL，并有超时（默认 600 秒，超时即结束进程树并使测试失败）。
- run_ok() 断言 prepare 成功（原函数忽略 prepare 的结果）。
- 环境隔离见上。

API 概要（详见各函数 docstring）
------------------------------
模块函数：kit_dir()、stub_pi_path()、legacy_source_digest()、legacy_facts()、load_legacy_module()、
isolated_env()、assert_isolated()、filter_path()、make_fake_pi()、ok_events()、assistant_message()、report_text()、
OK_FILES、contract()、build_md()、default_checks()、jload()、alive()、kill_hard()、kill_tree()、remove_tree()、
find_bash()、send_interrupt()、wait_for()、sha256_file()、make_temp_area()；异常 CleanupOwnershipError；常量
TEMP_AREA_PREFIX、OWNER_MARKER_NAME。
LegacyCase（unittest.TestCase 基类）：make_repo、write_config、write_plan、write_plan_raw、tool、tool_split、
wrapper、popen_tool、sh、git、rd、attempt_ref、state、state_record、jload、review、worktree_of、run_ok、fake_pi、
child_env、track_pid、wait_for、pd。

示例::

    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from legacy_harness import LegacyCase, ok_events, OK_FILES

    class HappyPath(LegacyCase):
        def test_pass(self):
            repo, base = self.make_repo("happy")
            code, out = self.run_ok(repo)                       # prepare + run（stub 场景 ok）
            self.assertEqual((code, self.state(repo)), (0, "NEEDS_REVIEW"), out)
            code, out = self.tool(repo, "check", self.attempt_ref(1))
            self.assertEqual(code, 0, out)
            code, out = self.tool(repo, "verdict", self.attempt_ref(1), "--verdict", "PASS",
                                  "--review", self.review(repo, "PASS"))
            self.assertEqual((code, self.state(repo)), (0, "PASS"), out)

        def test_custom_stream(self):
            repo, base = self.make_repo("fake")
            events = ok_events(settled=False)                   # 去掉 agent_settled
            pi = self.fake_pi(events, exit_code=0, files=OK_FILES)
            self.tool(repo, "prepare", "normalize-query.v1")
            code, out = self.tool(repo, "run", self.attempt_ref(1), pi_cmd=pi)
            summary = self.jload(self.rd(repo) / "events-summary.json")

平台注意（Windows Server 2025、Python 3.12、Git for Windows）
-----------------------------------------------------------
- 与原夹具一样用 Path.write_text 写文件：Windows 上 "\\n" 会写成 CRLF（临时仓库 core.autocrlf=false，所以
  提交进去的就是 CRLF）；stub 与假 pi 的事件行默认也是 CRLF（line_ending="native"），真实 pi（Node）是 LF，
  需要时传 line_ending="lf"。
- 输出按 UTF-8（errors="replace"）解码、stdout 与 stderr 合并，不做换行归一：Windows 上是 CRLF。
- send_interrupt() 在 Windows 上发送 CTRL_BREAK_EVENT，要求目标用 popen_tool(new_process_group=True) 启动，
  且当前进程有控制台；没有控制台时 Windows 会报错（原样抛出）。Windows 上 SIGBREAK 不会打断 Python 的单次长
  time.sleep（处理函数要等 sleep 返回才运行）；调度器的监督循环是短轮询，本机实测约 2 秒内响应。
- Windows 的 TEMP 常为 8.3 短名（ADMINI~1）；self.work 已 resolve 为长名，与调度器记录的路径一致。比较路径时
  仍建议两边都 resolve()。
- alive() 在 Windows 上用 tasklist；kill_tree() 用 taskkill /T /F；进程号可能被系统复用。
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import platform
import re
import secrets
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

__all__ = [
    "HERE", "REPO_ROOT", "PY", "IS_WINDOWS", "KIT_ENV_VAR", "SOURCE_REVISION", "LOCKED_PI_DISPATCH_SHA256",
    "TASK_ID", "PLAN_KEY", "DEFAULT_TOOL_TIMEOUT", "DEFAULT_GITIGNORE", "IsolationError",
    "kit_dir", "stub_pi_path", "sha256_file", "legacy_source_digest", "legacy_facts", "load_legacy_module",
    "filter_path", "isolated_env", "assert_isolated", "make_fake_pi", "assistant_message", "report_text",
    "ok_events", "OK_FILES", "DEFAULT_USAGE", "DEFAULT_REPORT", "default_checks", "contract", "build_md", "jload",
    "alive", "kill_hard", "kill_tree", "remove_tree", "find_bash", "send_interrupt", "wait_for", "LegacyCase",
    "TEMP_AREA_PREFIX", "OWNER_MARKER_NAME", "CleanupOwnershipError", "make_temp_area",
]

# ---------------------------------------------------------------------------
# 常量（导入时只做路径解析）
# ---------------------------------------------------------------------------

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
PY = sys.executable
IS_WINDOWS = os.name == "nt"
KIT_ENV_VAR = "CODEKIT_LEGACY_KIT_DIR"
SOURCE_REVISION = "a4fa199b0e5bdc658215765ee7558b9fe6723940"
#: scripts/pi_dispatch.py 在 a4fa199 的字节摘要（与 tests/codekit01_legacy.py:62 的 LEGACY_PI_DISPATCH_SHA256 相同）。
LOCKED_PI_DISPATCH_SHA256 = "a00d693452b4345d6093efa9864de6e1b4cefacece867b617e68e6a8efce3ad4"
TASK_ID = "normalize-query"
PLAN_KEY = "normalize-query.v1"
DEFAULT_TOOL_TIMEOUT = 600.0
#: tests/test_dispatch.py:169 make_repo 的 gitignore 默认值。
DEFAULT_GITIGNORE = ".agent/runs/\n.env\nnode_modules/\n"

AGENT_CLI_NAMES = ("pi", "claude", "codex")
AGENT_CLI_EXTS = ("", ".exe", ".cmd", ".bat", ".ps1", ".com")
SECRET_NAME_RE = re.compile(r"(?i)(token|secret|password|credential|api_?key|auth)")
#: 按前缀删除的变量（大小写不敏感）。PI_DISPATCH_PI_CMD 与 GIT_CONFIG_GLOBAL 删除后由本工具重设。
REMOVED_PREFIXES = ("PI_EXEC_", "STUB_", "PI_DISPATCH_", "GIT_CONFIG")
#: 按名字删除的变量（大小写不敏感）：Git 仓库重定向、提交者身份、影响子 Python 的启动变量。
REMOVED_NAMES = frozenset((
    "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR", "GIT_NAMESPACE", "GIT_PREFIX", "GIT_CEILING_DIRECTORIES", "GIT_DISCOVERY_ACROSS_FILESYSTEM",
    "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL", "GIT_COMMITTER_DATE",
    "PYTHONPATH", "PYTHONSTARTUP", "PYTHONIOENCODING", "PYTHONUTF8", "PYTHONWARNINGS",
    "PI_CODING_AGENT_DIR",
))


class IsolationError(RuntimeError):
    """受控环境不成立（例如 PATH 中仍能找到真实的 pi/claude/codex）；这时不启动任何子进程。"""


# ---------------------------------------------------------------------------
# 被测源码（KIT）与来源记录
# ---------------------------------------------------------------------------

def kit_dir() -> Path:
    """被测源码目录：CODEKIT_LEGACY_KIT_DIR（若设置）或本仓库根目录；缺少被测脚本时报错。"""
    override = os.environ.get(KIT_ENV_VAR)
    kit = Path(override).expanduser().resolve() if override else REPO_ROOT
    for rel in ("scripts/pi_dispatch.py", "scripts/dispatch-pi.sh"):
        if not (kit / rel).is_file():
            raise RuntimeError("被测源码目录 %s 中缺少 %s（%s=%s）" % (kit, rel, KIT_ENV_VAR, "已设置" if override else "未设置"))
    return kit


def stub_pi_path(kit: Optional[Path] = None) -> Path:
    """KIT/tests/stub_pi.py；KIT 中没有时退回本文件所在目录的 stub_pi.py。"""
    kit = kit or kit_dir()
    candidate = kit / "tests" / "stub_pi.py"
    return candidate if candidate.is_file() else HERE / "stub_pi.py"


def sha256_file(path: Union[str, Path]) -> str:
    digest = hashlib.sha256()
    with open(str(path), "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def legacy_source_digest(kit: Optional[Path] = None) -> str:
    """KIT/scripts/pi_dispatch.py 的 sha256（十六进制小写），写进测试报告，说明被测的是哪份字节。"""
    return sha256_file((kit or kit_dir()) / "scripts" / "pi_dispatch.py")


def legacy_facts(kit: Optional[Path] = None) -> Dict[str, Any]:
    """被测来源与本机事实（不含环境变量值）：供测试报告记录“测的是什么、在哪测的”。

    pi_dispatch_sha256 是 KIT 中原始字节的摘要；pi_dispatch_sha256_lf 是把 CRLF 归一为 LF 之后的摘要。
    pi_dispatch_matches_a4fa199 用后者与锁定值（a4fa199 的 blob 字节，LF 行尾）比较：该文件没有 eol 属性，本机
    系统级 core.autocrlf=true，重新检出、新克隆或新建 worktree 得到的是 CRLF 字节，内容仍是 a4fa199（Python 编译时
    两种行尾等价）。LF 工作区中两个摘要相同。
    """
    kit = kit or kit_dir()
    stub = stub_pi_path(kit)
    digest = legacy_source_digest(kit)
    digest_lf = hashlib.sha256((kit / "scripts" / "pi_dispatch.py").read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    return {
        "kit_dir": str(kit),
        "kit_overridden": bool(os.environ.get(KIT_ENV_VAR)),
        "pi_dispatch_sha256": digest,
        "pi_dispatch_sha256_lf": digest_lf,
        "pi_dispatch_matches_a4fa199": digest_lf == LOCKED_PI_DISPATCH_SHA256,
        "locked_pi_dispatch_sha256": LOCKED_PI_DISPATCH_SHA256,
        "source_revision": SOURCE_REVISION,
        "dispatch_sh_sha256": sha256_file(kit / "scripts" / "dispatch-pi.sh"),
        "stub_pi": str(stub),
        "stub_pi_sha256": sha256_file(stub),
        "stub_from_kit": stub.parent.resolve() == (kit / "tests").resolve(),
        "harness_sha256": sha256_file(Path(__file__).resolve()),
        "python": platform.python_version(),
        "python_executable": PY,
        "platform": platform.platform(),
        "os_name": os.name,
    }


_LEGACY_MODULES: Dict[str, types.ModuleType] = {}


def load_legacy_module(kit: Optional[Path] = None) -> types.ModuleType:
    """在进程内加载 KIT/scripts/pi_dispatch.py（从读到的同一份字节编译执行，不经 import、不写字节码）。

    对应 tests/test_dispatch.py:39-40 的 ``import pi_dispatch as pd``，用于 EXIT_* 常量与 pd.set_state 等。
    同一份字节只加载一次；模块名带摘要前缀，与 test_dispatch 的 pi_dispatch、codekit01_legacy 的模块互不影响。
    """
    path = (kit or kit_dir()) / "scripts" / "pi_dispatch.py"
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    cached = _LEGACY_MODULES.get(digest)
    if cached is not None:
        return cached
    name = "codekit_legacy_harness_pd_%s" % digest[:12]
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    try:
        exec(compile(raw, str(path), "exec"), module.__dict__)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    _LEGACY_MODULES[digest] = module
    return module


# ---------------------------------------------------------------------------
# 环境隔离（01-L05）
# ---------------------------------------------------------------------------

def _is_within(child: Union[str, Path], parent: Union[str, Path]) -> bool:
    try:
        c = Path(child).resolve()
        p = Path(parent).resolve()
    except (OSError, RuntimeError):
        return False
    cn, pn = os.path.normcase(str(c)), os.path.normcase(str(p))
    return cn == pn or cn.startswith(pn.rstrip("\\/") + os.sep)


def _agent_cli_exts(env: Optional[Mapping[str, str]] = None) -> Tuple[str, ...]:
    exts = list(AGENT_CLI_EXTS)
    source = env if env is not None else os.environ
    pathext = _env_get(source, "PATHEXT") or ""
    for ext in pathext.split(os.pathsep):
        ext = ext.strip().lower()
        if ext and ext not in exts:
            exts.append(ext)
    return tuple(exts)


def _dir_agent_clis(directory: str, exts: Sequence[str]) -> List[str]:
    """目录中存在的 pi/claude/codex 可执行文件名（只看文件是否存在，不执行）。"""
    found = []
    for name in AGENT_CLI_NAMES:
        for ext in exts:
            if os.path.lexists(os.path.join(directory, name + ext)):
                found.append(name + ext)
    return found


#: (PATH 条目, 扩展名) → 该目录是否含 pi/claude/codex。只缓存用例临时区域之外的目录（宿主目录），
#: 用例临时区域内的目录每次重新检查（测试可能在其中新建假 pi）。
_HOST_DIR_CACHE: Dict[Tuple[str, Tuple[str, ...]], bool] = {}


def _host_dir_has_agent_cli(directory: str, exts: Tuple[str, ...]) -> bool:
    key = (directory, exts)
    if key not in _HOST_DIR_CACHE:
        _HOST_DIR_CACHE[key] = bool(_dir_agent_clis(directory, exts))
    return _HOST_DIR_CACHE[key]


def _env_key(env: Mapping[str, str], name: str) -> Optional[str]:
    if name in env:
        return name
    if IS_WINDOWS:
        upper = name.upper()
        for key in env:
            if key.upper() == upper:
                return key
    return None


def _env_get(env: Mapping[str, str], name: str) -> Optional[str]:
    key = _env_key(env, name)
    return env[key] if key is not None else None


def _env_set(env: Dict[str, str], name: str, value: Optional[str]) -> None:
    """设置或删除（value 为 None）变量；Windows 上变量名不区分大小写，先去掉同名的其他写法。"""
    for key in [k for k in env if (k.upper() == name.upper() if IS_WINDOWS else k == name)]:
        del env[key]
    if value is not None:
        env[name] = value


def filter_path(path_value: str, env: Optional[Mapping[str, str]] = None) -> Tuple[str, Dict[str, int]]:
    """去掉 PATH 中的空条目、相对条目和含 pi/claude/codex 的目录；返回 (新 PATH, 各类计数)。"""
    exts = _agent_cli_exts(env)
    kept: List[str] = []
    counts = {"entries": 0, "kept": 0, "removed_agent_cli_dirs": 0, "removed_empty": 0, "removed_relative": 0}
    for entry in (path_value or "").split(os.pathsep):
        counts["entries"] += 1
        raw = entry.strip().strip('"')
        if not raw:
            counts["removed_empty"] += 1
            continue
        if not os.path.isabs(raw):
            counts["removed_relative"] += 1
            continue
        if _dir_agent_clis(raw, exts):
            counts["removed_agent_cli_dirs"] += 1
            continue
        kept.append(entry)
    counts["kept"] = len(kept)
    return os.pathsep.join(kept), counts


def assert_isolated(env: Mapping[str, str], allowed_roots: Sequence[Union[str, Path]] = (),
                    check_names: bool = True) -> None:
    """复核受控环境；不成立时抛 IsolationError（不启动任何子进程）。

    - PATH 中含 pi/claude/codex 的目录只能位于 allowed_roots（用例的临时区域）之内，且不允许相对条目；
    - PI_DISPATCH_PI_CMD 必须存在；若能解析为 JSON 字符串数组，其中名为 pi/claude/codex 的程序只能位于
      allowed_roots 之内；不能解析时按旧实现当作单个可执行文件路径，同样核对；
    - PI_CODING_AGENT_DIR 必须存在，并位于 allowed_roots 之内（有 allowed_roots 时）；
    - check_names=True 时，不得残留按名字应删除的变量（测试显式传入的变量在复核时用 check_names=False）。
    """
    exts = _agent_cli_exts(env)
    for entry in (_env_get(env, "PATH") or "").split(os.pathsep):
        raw = entry.strip().strip('"')
        if not raw:
            continue
        if not os.path.isabs(raw):
            raise IsolationError("PATH 含相对条目，无法确定会找到哪个 pi/claude/codex")
        if any(_is_within(raw, root) for root in allowed_roots):
            continue
        if _host_dir_has_agent_cli(raw, exts):
            raise IsolationError("PATH 中仍有含 pi/claude/codex 的目录（不在用例临时区域内）")
    pi_cmd = _env_get(env, "PI_DISPATCH_PI_CMD")
    if not pi_cmd:
        raise IsolationError("PI_DISPATCH_PI_CMD 未设置：旧实现会按 PATH 查找真实的 pi")
    try:
        value = json.loads(pi_cmd)
    except ValueError:
        value = [pi_cmd]
    programs = value if isinstance(value, list) else [pi_cmd]
    for item in programs:
        if not isinstance(item, str) or not item:
            continue
        stem = Path(item).name.lower()
        base = stem.rsplit(".", 1)[0] if "." in stem else stem
        if base in AGENT_CLI_NAMES and not any(_is_within(item, root) for root in allowed_roots):
            raise IsolationError("PI_DISPATCH_PI_CMD 指向用例临时区域之外名为 %s 的程序" % base)
    agent_dir = _env_get(env, "PI_CODING_AGENT_DIR")
    if not agent_dir:
        raise IsolationError("PI_CODING_AGENT_DIR 未设置：旧实现会读取真实的 ~/.pi/agent")
    if allowed_roots and not any(_is_within(agent_dir, root) for root in allowed_roots):
        raise IsolationError("PI_CODING_AGENT_DIR 不在用例临时区域内")
    if check_names:
        for name in env:
            upper = name.upper()
            if name.upper() in ("PI_DISPATCH_PI_CMD", "GIT_CONFIG_GLOBAL"):
                continue
            if upper.startswith(REMOVED_PREFIXES) or upper in (REMOVED_NAMES - {"PI_CODING_AGENT_DIR"}) \
                    or SECRET_NAME_RE.search(name):
                raise IsolationError("环境中残留应删除的变量：%s" % name)


def isolated_env(pi_cmd: Sequence[str], agent_dir: Union[str, Path],
                 git_global_config: Optional[Union[str, Path]] = None,
                 base: Optional[Mapping[str, str]] = None,
                 allowed_roots: Sequence[Union[str, Path]] = ()) -> Tuple[Dict[str, str], Dict[str, Any]]:
    """由 os.environ（或 base）生成受控环境，返回 (env, report)。对应 tests/test_dispatch.py:28-32 的 BASE_ENV。

    pi_cmd：写入 PI_DISPATCH_PI_CMD 的 argv（JSON 数组）；agent_dir：PI_CODING_AGENT_DIR（应是空目录）；
    git_global_config：不为 None 时设为 GIT_CONFIG_GLOBAL（应是空文件）。
    report 只含变量名与计数，不含任何变量值。隔离后 PATH 中找不到 git 时抛 IsolationError。
    """
    source = dict(os.environ if base is None else base)
    env: Dict[str, str] = {}
    removed: List[str] = []
    for name, value in source.items():
        upper = name.upper()
        if upper.startswith(REMOVED_PREFIXES) or upper in REMOVED_NAMES or SECRET_NAME_RE.search(name):
            removed.append(name)
            continue
        env[name] = value
    path_key = _env_key(env, "PATH") or "PATH"
    new_path, counts = filter_path(env.get(path_key, ""), env)
    env[path_key] = new_path
    _env_set(env, "PI_DISPATCH_PI_CMD", json.dumps([str(x) for x in pi_cmd]))
    _env_set(env, "PI_CODING_AGENT_DIR", str(agent_dir))
    if git_global_config is not None:
        _env_set(env, "GIT_CONFIG_GLOBAL", str(git_global_config))
    _env_set(env, "PYTHONDONTWRITEBYTECODE", "1")
    _env_set(env, "GIT_TERMINAL_PROMPT", "0")
    _env_set(env, "GCM_INTERACTIVE", "never")
    assert_isolated(env, allowed_roots)
    if not shutil.which("git", path=new_path):
        raise IsolationError("隔离后的 PATH 中找不到 git（git 与 pi/claude/codex 在同一目录？）")
    report = {
        "removed_env_names": sorted(removed),
        "path": counts,
        "which_after": {name: shutil.which(name, path=new_path) is not None
                        for name in ("git", "bash") + AGENT_CLI_NAMES},
        "pi_cmd": [str(x) for x in pi_cmd],
        "agent_dir": str(agent_dir),
        "git_config_global": str(git_global_config) if git_global_config is not None else None,
    }
    return env, report


# ---------------------------------------------------------------------------
# 假 pi（stub_pi.py 没有的场景；不修改 stub_pi.py）
# ---------------------------------------------------------------------------

_FAKE_PI_TEMPLATE = r'''# -*- coding: utf-8 -*-
"""假 pi：由 tests/legacy_harness.py 的 make_fake_pi 生成，不调用模型、不联网。配置内嵌在本文件中。"""
import base64
import json
import os
import subprocess
import sys
import time
from pathlib import Path

CONFIG = json.loads(__CONFIG__)
args = sys.argv[1:]
EOL = "\r\n" if CONFIG["line_ending"] == "native" and os.name == "nt" else "\n"


def opt(name):
    if name in args:
        i = args.index(name)
        return args[i + 1] if i + 1 < len(args) else None
    return None


def log(mode):
    path = CONFIG.get("argv_log")
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps({"mode": mode, "argv": args, "cwd": os.getcwd()}, ensure_ascii=False) + "\n")


def write(stream, text):
    """原样写出（不转换行尾）。"""
    stream.buffer.write(text.encode("utf-8"))
    stream.flush()


def say(text):
    """同 print：末尾加换行，并按 line_ending 转换行尾。"""
    write(sys.stdout, (text + "\n").replace("\n", EOL))


if "--help" in args:
    log("help")
    say(CONFIG["help_text"])
    sys.exit(CONFIG["help_exit_code"])
if "--version" in args:
    log("version")
    if CONFIG["version"] is not None:
        say(CONFIG["version"])
    sys.exit(CONFIG["version_exit_code"])
if args and args[0] == "auth":
    log("auth")
    status = CONFIG["auth_status"]
    say(json.dumps({"status": status, "provider": opt("--provider"), "model": opt("--model")}))
    code = CONFIG["auth_exit_code"]
    sys.exit(code if code is not None else (0 if status == "ready" else 1))
if "--list-models" in args:
    log("list-models")
    if CONFIG["list_models_stderr"]:
        write(sys.stderr, CONFIG["list_models_stderr"])
    if CONFIG["list_models_output"] is not None:
        write(sys.stdout, CONFIG["list_models_output"])
        sys.exit(CONFIG["list_models_exit_code"])
    if CONFIG["list_models_exit_code"] != 0:
        sys.exit(CONFIG["list_models_exit_code"])
    pattern = opt("--list-models")
    pairs = CONFIG["models"]
    if not pairs:
        say("No models available. Use /login to log into a provider via OAuth or API key. See:")
        say("  /pi/docs/providers.md")
        sys.exit(0)
    shown = [p for p in pairs if not pattern or pattern.startswith("-") or pattern in " ".join(p)]
    if not shown:
        say('No models matching "%s"' % pattern)
        sys.exit(0)
    say("provider    model                     context  max-out  thinking  images")
    for provider, model in shown:
        say("%-11s %-25s 256K     230.4K   yes       no" % (provider, model))
    sys.exit(0)

log("run")
cwd = Path.cwd()
for spec in CONFIG["files"]:
    target = cwd / spec["path"]
    if spec["kind"] == "delete":
        if target.exists():
            target.unlink()
        continue
    target.parent.mkdir(parents=True, exist_ok=True)
    if spec["kind"] == "bytes":
        target.write_bytes(base64.b64decode(spec["b64"]))
    else:
        target.write_text(spec["text"], encoding="utf-8")
if CONFIG["grandchild_pid_file"]:
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(%d)" % CONFIG["grandchild_seconds"]])
    (cwd / CONFIG["grandchild_pid_file"]).write_text(str(child.pid), encoding="utf-8")
if CONFIG["stderr_text"]:
    write(sys.stderr, CONFIG["stderr_text"])
subs = {"{{provider}}": opt("--provider") or "", "{{model}}": opt("--model") or "",
        "{{thinking}}": opt("--thinking") or "", "{{cwd}}": str(cwd)}
subs = dict((k, json.dumps(v)[1:-1]) for k, v in subs.items())
for item in CONFIG["events"]:
    if item["kind"] == "sleep":
        time.sleep(item["seconds"])
        continue
    if item["kind"] == "raw":
        sys.stdout.buffer.write(base64.b64decode(item["b64"]))
    else:
        text = item["text"]
        for key, value in subs.items():
            text = text.replace(key, value)
        sys.stdout.buffer.write((text + EOL).encode("utf-8"))
    sys.stdout.flush()
    if CONFIG["event_delay"]:
        time.sleep(CONFIG["event_delay"])
if CONFIG["hang_seconds"]:
    time.sleep(CONFIG["hang_seconds"])
sys.exit(CONFIG["exit_code"])
'''

EventLine = Union[Mapping[str, Any], List[Any], str, bytes]


def _encode_event(item: EventLine) -> Dict[str, Any]:
    if isinstance(item, bytes):
        return {"kind": "raw", "b64": base64.b64encode(item).decode("ascii")}
    if isinstance(item, str):
        return {"kind": "text", "text": item}
    if isinstance(item, Mapping) and set(item.keys()) == {"__sleep__"}:
        return {"kind": "sleep", "seconds": float(item["__sleep__"])}
    return {"kind": "text", "text": json.dumps(item)}


def make_fake_pi(directory: Union[str, Path], events_lines: Iterable[EventLine], exit_code: int = 0,
                 help_text: Optional[str] = None, version: Optional[str] = "0.87.0", *,
                 name: str = "fake_pi.py",
                 models: Sequence[Sequence[str]] = (("step", "step-5-preview"),),
                 list_models_exit_code: int = 0, list_models_output: Optional[str] = None,
                 list_models_stderr: str = "",
                 auth_status: str = "ready", auth_exit_code: Optional[int] = None,
                 help_exit_code: int = 0, version_exit_code: int = 0,
                 stderr_text: str = "",
                 files: Optional[Mapping[str, Union[str, bytes, None]]] = None,
                 event_delay: float = 0.0, hang_seconds: float = 0.0,
                 grandchild_pid_file: Optional[str] = None, grandchild_seconds: int = 600,
                 line_ending: str = "native",
                 argv_log: Optional[Union[str, Path]] = None,
                 kit: Optional[Path] = None) -> List[str]:
    """生成一个自带配置的假 pi 脚本，返回可放进 PI_DISPATCH_PI_CMD 的 argv：[sys.executable, <脚本>]。

    子命令的识别顺序与 tests/stub_pi.py:33-65 相同：--help、--version、auth、--list-models，其余为运行模式。
    - events_lines（运行模式按顺序输出到 stdout）：
      dict/list → json.dumps（ASCII）后加行尾；str → 原样加行尾（应是一行 JSON 文本，也可以是不可解析的行）；
      bytes → 原样写出、不加行尾（用于截断行、特殊字节）；{"__sleep__": 秒} → 暂停。
      dict/str 中的 {{provider}}、{{model}}、{{thinking}}、{{cwd}} 在运行时替换为实际参数与工作目录
      （按 JSON 字符串转义，适合出现在 JSON 字符串值里）。
    - exit_code：运行模式的退出码；stderr_text：运行模式开始时写到 stderr 的文字。
    - help_text：默认取 stub 所在目录的 stub_pi_help.txt（与 stub 相同，预检能通过）；help_exit_code。
    - version：--version 的输出（None 表示不输出）；version_exit_code。
    - models / list_models_*：--list-models 的模拟（与 stub 一样按参数筛选；list_models_output 给定时原样输出）。
    - auth_status / auth_exit_code：pi auth check 的模拟（默认 ready → 0，其余 → 1）。
    - files：运行模式开始时在工作目录写入的文件 {相对路径: str（Path.write_text，Windows 上为 CRLF，同 stub）
      | bytes（原样）| None（删除）}。
    - event_delay：每行之后暂停的秒数；hang_seconds：输出完全部行后、退出前暂停的秒数（用于超时、取消）。
    - grandchild_pid_file：运行模式开始时起一个睡眠 grandchild_seconds 秒的孙进程，把 PID 写到工作目录下这个文件
      （同 stub 的 hang 场景）；调用方负责结束它（LegacyCase.track_pid）。
    - line_ending："native"（默认，Windows 上 CRLF，与 stub 一致）或 "lf"（与真实 pi/Node 一致）。
    - argv_log：每次调用向该文件追加一行 {"mode", "argv", "cwd"}（放在用例临时区域内，勿放进被测仓库）。
    """
    if line_ending not in ("native", "lf"):
        raise ValueError("line_ending 必须是 native 或 lf")
    if help_text is None:
        help_text = (stub_pi_path(kit).parent / "stub_pi_help.txt").read_text(encoding="utf-8")
    file_specs = []
    for rel, value in (files or {}).items():
        if value is None:
            file_specs.append({"path": rel, "kind": "delete"})
        elif isinstance(value, bytes):
            file_specs.append({"path": rel, "kind": "bytes", "b64": base64.b64encode(value).decode("ascii")})
        else:
            file_specs.append({"path": rel, "kind": "text", "text": value})
    config = {
        "events": [_encode_event(item) for item in events_lines],
        "exit_code": int(exit_code), "help_text": help_text, "help_exit_code": int(help_exit_code),
        "version": version, "version_exit_code": int(version_exit_code),
        "models": [list(pair) for pair in models], "list_models_exit_code": int(list_models_exit_code),
        "list_models_output": list_models_output, "list_models_stderr": list_models_stderr,
        "auth_status": auth_status, "auth_exit_code": auth_exit_code,
        "stderr_text": stderr_text, "files": file_specs, "event_delay": float(event_delay),
        "hang_seconds": float(hang_seconds), "grandchild_pid_file": grandchild_pid_file,
        "grandchild_seconds": int(grandchild_seconds), "line_ending": line_ending,
        "argv_log": str(argv_log) if argv_log is not None else None,
    }
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    script = directory / name
    source = _FAKE_PI_TEMPLATE.replace("__CONFIG__", repr(json.dumps(config, ensure_ascii=True)))
    script.write_bytes(source.encode("utf-8"))
    return [PY, str(script)]


#: tests/stub_pi.py:103-104 的用量与费用。
DEFAULT_USAGE: Dict[str, Any] = {
    "input": 1000, "output": 200, "cacheRead": 0, "cacheWrite": 0, "totalTokens": 1200,
    "cost": {"input": 0.0002, "output": 0.00023, "cacheRead": 0, "cacheWrite": 0, "total": 0.00043}}
#: tests/stub_pi.py:212-215 的执行报告。
DEFAULT_REPORT: Dict[str, Any] = {
    "task_id": "normalize-query", "plan_version": 1, "attempt_id": "x", "executor_status": "completed",
    "changed_files": ["src/normalize.py", "tests/test_normalize.py"],
    "self_checks": [{"id": "V01", "command": "python run_tests.py", "reported_exit_code": 0}],
    "dod": [{"id": "D01", "status": "done"}], "unresolved_questions": [], "limitations": []}
#: tests/stub_pi.py:141-146 在 ok 场景写入的两个文件（给 make_fake_pi 的 files 用）。
OK_FILES: Dict[str, str] = {
    "src/normalize.py": "def normalize(q):\n    return ' '.join(q.split()).lower()\n",
    "tests/test_normalize.py": (
        "import unittest\nfrom normalize import normalize\n\n\nclass T(unittest.TestCase):\n"
        "    def test_spaces(self):\n        self.assertEqual(normalize('  A  B '), 'a b')\n\n"
        "    def test_empty(self):\n        self.assertEqual(normalize(''), '')\n"),
}


def assistant_message(content: List[Any], stop: str, *, provider: str = "{{provider}}", model: str = "{{model}}",
                      response_model: Optional[str] = None, usage: Optional[Mapping[str, Any]] = None,
                      error: Optional[str] = None, extra: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """与 tests/stub_pi.py:109-116 的 assistant() 同形的 assistant 消息；extra 可加 providerThinkingLevel 等字段。"""
    msg: Dict[str, Any] = {"role": "assistant", "content": content, "api": "anthropic-messages",
                           "provider": provider, "model": model,
                           "responseModel": model if response_model is None else response_model,
                           "usage": json.loads(json.dumps(usage if usage is not None else DEFAULT_USAGE)),
                           "stopReason": stop, "timestamp": 1}
    if error:
        msg["errorMessage"] = error
    if extra:
        msg.update(extra)
    return msg


def report_text(report: Optional[Mapping[str, Any]] = None) -> str:
    """与 tests/stub_pi.py:220 相同格式的最终消息文字（执行报告 + JSON 代码块）。"""
    body = json.dumps(dict(report if report is not None else DEFAULT_REPORT), ensure_ascii=False, indent=2)
    return "## 执行报告\nD01 完成。\n\n```json\n%s\n```\n" % body


def ok_events(*, provider: str = "{{provider}}", model: str = "{{model}}", response_model: Optional[str] = None,
              usage: Optional[Mapping[str, Any]] = None, final_text: Optional[str] = None,
              report: Optional[Mapping[str, Any]] = None, stop_reason: str = "stop",
              error_message: Optional[str] = None, settled: bool = True,
              message_extra: Optional[Mapping[str, Any]] = None,
              tool_paths: Sequence[str] = ("src/normalize.py", "tests/test_normalize.py")) -> List[Dict[str, Any]]:
    """复现 tests/stub_pi.py ok 场景（:72、:125-234）的事件序列（dict 列表），供测试按需增删改后交给 make_fake_pi。

    error_message 给定时最终消息为 stub 的 error 形态（content 为空、stopReason=error）；settled=False 时去掉
    agent_settled（同 nosettle）。文件改动不在事件里，需另把 OK_FILES 传给 make_fake_pi(files=...)。
    """
    kw = dict(provider=provider, model=model, response_model=response_model, usage=usage, extra=message_extra)
    first = assistant_message([{"type": "toolCall", "id": "c1", "name": "write", "arguments": {}}], "toolUse", **kw)
    events: List[Dict[str, Any]] = [
        {"type": "session", "version": 3, "id": "stub", "timestamp": "2026-09-22T00:00:00Z", "cwd": "{{cwd}}"},
        {"type": "agent_start"},
        {"type": "turn_start"},
        {"type": "message_start", "message": {"role": "system", "content": ""}},
        {"type": "message_end", "message": {"role": "system", "content": "", "sections": {"base": "x", "context": "y"}}},
        {"type": "message_start", "message": first},
        {"type": "message_update", "usage": json.loads(json.dumps(usage if usage is not None else DEFAULT_USAGE)),
         "assistantMessageEvent": {"type": "text_delta", "delta": "x"}},
        {"type": "message_end", "message": first},
    ]
    for path in tool_paths:
        events.append({"type": "tool_execution_start", "toolCallId": "c1", "toolName": "write", "args": {"path": path}})
        events.append({"type": "tool_execution_end", "toolCallId": "c1", "toolName": "write", "result": {},
                       "isError": False})
    events += [{"type": "turn_end", "message": first, "toolResults": []}, {"type": "turn_start"}]
    if error_message:
        final = assistant_message([], "error", error=error_message, **kw)
    else:
        text = final_text if final_text is not None else report_text(report)
        final = assistant_message([{"type": "text", "text": text}], stop_reason, **kw)
    events += [{"type": "message_start", "message": final}, {"type": "message_end", "message": final},
               {"type": "turn_end", "message": final, "toolResults": []},
               {"type": "agent_end", "messages": [], "willRetry": False}]
    if settled:
        events.append({"type": "agent_settled"})
    return events


# ---------------------------------------------------------------------------
# 合同样本（与 tests/test_dispatch.py 相同）
# ---------------------------------------------------------------------------

def default_checks() -> List[Dict[str, Any]]:
    """tests/test_dispatch.py:103-105。"""
    return [{"id": "V01", "argv": [PY, "run_tests.py"], "cwd": ".", "timeout_seconds": 120,
             "required": True, "expected_exit_code": 0, "output_must_match": ["Tests [1-9][0-9]* passed"]}]


def contract(base: str, ver: int = 1, attempts: int = 3, thinking: str = "high", **over: Any) -> Dict[str, Any]:
    """tests/test_dispatch.py:108-125：合同 JSON 样本；over 覆盖顶层键。"""
    data: Dict[str, Any] = {
        "schema_version": 1, "task_id": "normalize-query", "plan_version": ver, "repository": "test",
        "base_sha": base, "risk_level": "low",
        "authorization": {"executor": ["local_edit", "local_test"], "integration": ["local_branch"]},
        "executor": {"provider": "step", "model": "step-5-preview", "thinking": thinking,
                     "tools": ["read", "grep", "find", "ls", "edit", "write", "bash"], "context_files": "project"},
        "scope": {"allowed_modified_files": ["src/normalize.py"], "allowed_new_files": ["tests/test_normalize.py"],
                  "allowed_deleted_files": [], "forbidden_paths": ["package.json"], "dependency_changes": "forbidden"},
        "setup": [],
        "checks": default_checks(),
        "definition_of_done": [{"id": "D01", "text": "行为正确", "evidence": ["V01"]},
                               {"id": "D02", "text": "范围合规", "evidence": ["scope"]}],
        "budget": {"max_attempts_total": attempts, "max_wall_seconds_per_attempt": 600,
                   "max_wall_seconds_total": 1800, "cost_budget": None},
    }
    data.update(over)
    return data


def build_md(c: Mapping[str, Any]) -> str:
    """tests/test_dispatch.py:128-159：按合同 JSON 生成与之一致的 Markdown（逐字复现，校验器会比较两者）。"""
    ex = c["executor"] if isinstance(c.get("executor"), dict) else {}
    auth = c["authorization"] if isinstance(c.get("authorization"), dict) else {}
    scope = c["scope"] if isinstance(c.get("scope"), dict) else {}
    budget = c["budget"] if isinstance(c.get("budget"), dict) else {}

    def join(values: Any) -> str:
        return ", ".join(str(v) for v in values) if isinstance(values, list) else str(values)

    lines = ["# TASK: %s" % c["task_id"], "", "## Identity", "- plan_version: %s" % c["plan_version"],
             "- repository: test", "- base_sha: %s" % c["base_sha"], "- risk_level: %s" % c["risk_level"],
             "- authorized_actions: %s" % join(auth.get("executor", [])),
             "- integration_actions: %s" % (join(auth.get("integration", [])) or "none"),
             "- executor: %s/%s · thinking %s" % (ex.get("provider"), ex.get("model"), ex.get("thinking")), "",
             "## Goal", "normalize() 折叠空白并转小写。", "", "## Non-goals", "- 不改其他模块。", "",
             "## Repository facts", "- src/normalize.py 中的 normalize(q)。", "", "## Scope"]
    for key in ("allowed_modified_files", "allowed_new_files", "allowed_deleted_files", "forbidden_paths"):
        lines.append("- %s: %s" % (key, join(scope.get(key, [])) or "无"))
    lines += ["- dependency_changes: %s" % scope.get("dependency_changes", "forbidden"), "",
              "## Behavior contract", "- '  A  B ' -> 'a b'", "", "## Steps", "1. 实现。", "",
              "## Validation commands"]
    for item in c.get("checks", []) if isinstance(c.get("checks"), list) else []:
        if isinstance(item, dict) and isinstance(item.get("argv"), list) and item["argv"]:
            lines.append("- %s: %s %s" % (item.get("id"), Path(str(item["argv"][0])).stem,
                                          " ".join(str(a) for a in item["argv"][1:])))
    lines += ["", "## Definition of done"]
    for item in c.get("definition_of_done", []):
        if isinstance(item, dict):
            lines.append("- %s: %s；证据：%s。" % (item.get("id"), item.get("text"), join(item.get("evidence", []))))
    lines += ["", "## Stop conditions", "- 需要改范围外文件。", "", "## Budget"]
    for key in ("max_attempts_total", "max_wall_seconds_per_attempt", "max_wall_seconds_total"):
        lines.append("- %s: %s" % (key, budget.get(key)))
    lines += ["", "## Report back", "- 最后一条消息为执行报告。", "", "## Forbidden", "- 不提交。", ""]
    return "\n".join(lines)


def jload(path: Union[str, Path]) -> Any:
    """tests/test_dispatch.py:216-217。"""
    return json.loads(Path(path).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 进程与文件
# ---------------------------------------------------------------------------

def alive(pid: Union[int, str]) -> bool:
    """tests/test_dispatch.py:66-81：进程是否存活（Windows 用 tasklist；POSIX 的僵尸进程视为不存活）。"""
    pid = int(pid)
    if IS_WINDOWS:
        out = subprocess.run(["tasklist", "/FI", "PID eq %d" % pid, "/NH"], stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL).stdout
        return str(pid) in out.decode("utf-8", "replace").split()
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:
        with open("/proc/%d/stat" % pid) as handle:
            return handle.read().split(") ")[-1][:1] != "Z"
    except OSError:
        return True


def kill_hard(pid: Union[int, str]) -> None:
    """tests/test_dispatch.py:84-91：强制结束进程（Windows 为 taskkill /F /T，结束整棵进程树）。"""
    if IS_WINDOWS:
        subprocess.run(["taskkill", "/PID", str(pid), "/F", "/T"], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    else:
        try:
            os.kill(int(pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass


def kill_tree(proc: subprocess.Popen) -> None:
    """结束 Popen 启动的进程及其子进程：Windows 用 taskkill /T /F；POSIX 若为新会话则结束整个进程组。"""
    if proc.poll() is not None:
        return
    if IS_WINDOWS:
        kill_hard(proc.pid)
    else:
        try:
            if os.getpgid(proc.pid) == proc.pid:
                os.killpg(proc.pid, signal.SIGKILL)
            else:
                proc.kill()
        except (ProcessLookupError, PermissionError):
            pass
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=30)


# ---------------------------------------------------------------------------
# 临时区域与清理前的归属核对（01 文档 8.4；acceptance.md R-12、第 7 节第 17 项）
# ---------------------------------------------------------------------------
#
# 8.4 要求清理前同时核对预期父目录、本任务创建的随机目录名或标记、真实路径与任务所有权，不确定时不递归删除。
# 做法参照 tests/test_baseline_tool.py 的 TempArea（核对父目录与前缀），并补上它没有的标记文件与所有权核对：
# make_temp_area() 建区域时写入随机值标记，并在本进程内存中登记；remove_tree() 删除前逐项核对，任一项不成立
# 就抛 CleanupOwnershipError、不删除任何东西（测试报错，而不是误删）。
#
# 已知边界：核对与删除之间仍有时间窗（TOCTOU），本工具只用于测试自建的临时区域，不防同一账户下的并发篡改；
# 核对的是“本进程建立并登记的区域”，其他进程（包括另一个测试进程）建的 codekit-legacy-* 目录一律拒绝删除。

#: 本工具建的临时区域的目录名前缀（tempfile.mkdtemp 的 prefix）。
TEMP_AREA_PREFIX = "codekit-legacy-"
#: 临时区域根目录中的所有权标记文件名。内容是建区域时由 secrets.token_hex(32) 生成的随机值（64 个 ASCII 字符，
#: 不含换行）；期望值只记在本进程内存中，所以复制或伪造一个同名文件不足以通过核对。
OWNER_MARKER_NAME = ".codekit-legacy-owner"


class CleanupOwnershipError(RuntimeError):
    """清理前的归属核对不成立：拒绝删除（本次调用没有删除任何东西）。不是 OSError，remove_tree 不会重试它。"""


class _TempArea:
    """本进程用 make_temp_area() 建立并登记的一个临时区域。

    state："live"（可完整核对）；"marker_removed"（本进程已删完其中内容与标记，只剩空的根目录，此后只允许
    os.rmdir 这个空目录，非递归）；"removed"（已删除，此后区域内出现的任何路径都拒绝删除）。
    """

    __slots__ = ("root", "segments", "token", "identity", "state")

    def __init__(self, root: str, token: str, identity: Tuple[int, int]) -> None:
        self.root = root
        self.segments = _path_segments(root)
        self.token = token
        self.identity = identity
        self.state = "live"


#: 根目录真实路径（os.path.realpath 的原样字符串）→ 区域记录。只在 make_temp_area() 中增加；删除后保留记录
#: （state="removed"），以便对已删除区域内的路径给出确定的结论。导入时为空，不建目录、不写文件（01-L04）。
_TEMP_AREAS: Dict[str, _TempArea] = {}


def _path_segments(path: str) -> Tuple[str, ...]:
    """把绝对路径拆成 (驱动器或 UNC 前缀, 各级名字...)，供逐段精确比较。

    不做 os.path.normcase 的大小写折叠：两边都取 os.path.realpath，已存在的部分由系统给出实际写法；折叠大小写
    会把大小写敏感目录（Windows 可按目录开启）中的不同条目当成同一个。
    """
    drive, rest = os.path.splitdrive(path)
    if os.altsep:
        rest = rest.replace(os.altsep, os.sep)
    return (drive,) + tuple(part for part in rest.split(os.sep) if part)


def _is_link_like(path: str) -> bool:
    """path 本身（最后一段）是否为符号链接或 Windows 目录联接（junction）；不存在时为 False。"""
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return False
    if stat.S_ISLNK(st.st_mode):
        return True
    junction_tag = getattr(stat, "IO_REPARSE_TAG_MOUNT_POINT", None)
    return junction_tag is not None and getattr(st, "st_reparse_tag", None) == junction_tag


def _dir_identity(st: os.stat_result) -> Tuple[int, int]:
    return (st.st_dev, st.st_ino)


def _refuse(reason: str, path: str) -> CleanupOwnershipError:
    return CleanupOwnershipError("拒绝删除归属不明的路径（01 文档 8.4）：%s：%s" % (reason, path))


def _verify_area_location(area: _TempArea) -> None:
    """父目录与目录名：根目录必须是 realpath(tempfile.gettempdir()) 的直接子目录，目录名以 TEMP_AREA_PREFIX 开头。

    tempfile.gettempdir() 在核对时取值（首次调用可能在系统临时目录中探测可写性，所以不在导入时调用）。
    """
    base = _path_segments(os.path.realpath(tempfile.gettempdir()))
    if area.segments[:-1] != base:
        raise _refuse("不是系统临时目录的直接子目录（按路径分段比较）", area.root)
    if not area.segments[-1].startswith(TEMP_AREA_PREFIX):
        raise _refuse("目录名不以 %s 开头" % TEMP_AREA_PREFIX, area.root)


def _verify_area_root(area: _TempArea) -> os.stat_result:
    """根目录本身：真实路径与登记时相同、是目录而不是链接或联接、目录身份（st_dev, st_ino）与创建时相同。"""
    if _path_segments(os.path.realpath(area.root)) != area.segments:
        raise _refuse("真实路径与创建时不同", area.root)
    try:
        st = os.lstat(area.root)
    except FileNotFoundError:
        raise _refuse("临时区域根目录已不存在，无法核对标记", area.root) from None
    if not stat.S_ISDIR(st.st_mode) or _is_link_like(area.root):
        raise _refuse("根目录不是普通目录（可能是链接或联接）", area.root)
    if _dir_identity(st) != area.identity:
        raise _refuse("目录身份与创建时不同（目录被替换）", area.root)
    return st


def _verify_area_marker(area: _TempArea) -> None:
    """所有权标记：根目录中存在普通文件 OWNER_MARKER_NAME，内容与本进程创建时记录的随机值逐字节相同。"""
    marker = os.path.join(area.root, OWNER_MARKER_NAME)
    try:
        st = os.lstat(marker)
    except FileNotFoundError:
        raise _refuse("缺少所有权标记文件 %s" % OWNER_MARKER_NAME, area.root) from None
    if not stat.S_ISREG(st.st_mode) or _is_link_like(marker):
        raise _refuse("所有权标记不是普通文件", marker)
    expected = area.token.encode("ascii")
    with open(marker, "rb") as handle:
        data = handle.read(len(expected) + 1)
    if data != expected:
        raise _refuse("所有权标记内容与本进程创建时记录的随机值不一致", marker)


def _verify_area(area: _TempArea) -> None:
    """完整核对一个 live 区域：父目录与前缀、真实路径与目录身份、所有权标记。"""
    _verify_area_location(area)
    _verify_area_root(area)
    _verify_area_marker(area)


def make_temp_area() -> Path:
    """建立一个本用例专用的临时区域并登记所有权，返回其真实路径（已解析为长名，同原来的 mkdtemp(...).resolve()）。

    步骤：tempfile.mkdtemp(prefix=TEMP_AREA_PREFIX) → 记录根目录的真实路径与目录身份 → 以独占方式（"xb"）写入
    所有权标记 OWNER_MARKER_NAME（内容为 secrets.token_hex(32)）→ 立即按 remove_tree 的规则完整核对一次，
    不成立时（例如系统临时目录经链接解析后不是区域的父目录）当场失败，而不是留下一个以后删不掉的目录。
    失败时只撤销本函数刚建的东西：删除本函数创建的标记文件与空目录（os.rmdir，非递归），然后原样抛出。
    """
    created = tempfile.mkdtemp(prefix=TEMP_AREA_PREFIX)
    marker_path: Optional[str] = None
    try:
        root = os.path.realpath(created)
        identity = _dir_identity(os.lstat(root))
        token = secrets.token_hex(32)
        marker = os.path.join(root, OWNER_MARKER_NAME)
        with open(marker, "xb") as handle:
            marker_path = marker
            handle.write(token.encode("ascii"))
        area = _TempArea(root, token, identity)
        _verify_area(area)
    except BaseException:
        if marker_path is not None:
            try:
                os.unlink(marker_path)
            except OSError:
                pass
        try:
            os.rmdir(created)
        except OSError:
            pass
        raise
    _TEMP_AREAS[root] = area
    return Path(root)


def _owning_area(real: str) -> Optional[_TempArea]:
    segments = _path_segments(real)
    for area in _TEMP_AREAS.values():
        if segments[:len(area.segments)] == area.segments:
            return area
    return None


def _force_remove(func: Callable[..., Any], path: str, exc: Any) -> None:
    """shutil.rmtree 的失败处理：只读文件（Windows 上的 git 对象）改权限后重试一次。

    链接或联接不改权限（os.chmod 会跟随链接，改到区域之外的目标），原样抛出原来的异常。
    """
    if _is_link_like(path):
        raise exc if isinstance(exc, BaseException) else exc[1]
    os.chmod(path, 0o700)
    func(path)


def _rmtree(path: str) -> None:
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_force_remove)
    else:  # pragma: no cover - Python 3.10/3.11
        shutil.rmtree(path, onerror=_force_remove)


def _remove_entry(path: str) -> None:
    """删除区域根目录下的一个条目：链接、联接与文件只删条目本身（不跟随），普通目录递归删除。"""
    if _is_link_like(path):
        os.unlink(path)  # Windows 上 os.unlink 也能删除目录符号链接与联接，不进入其目标
    elif os.path.isdir(path):
        _rmtree(path)
    else:
        try:
            os.unlink(path)
        except PermissionError:
            os.chmod(path, 0o700)
            os.unlink(path)


def _remove_owned_once(path: Union[str, Path]) -> None:
    """核对归属后删除一次；核对不成立抛 CleanupOwnershipError（不删除），删除中的 OSError 原样抛出（由调用方重试）。"""
    raw = os.fspath(path)
    real = os.path.realpath(raw)
    area = _owning_area(real)
    if area is None:
        raise _refuse("不在本进程用 make_temp_area() 建立的临时区域内", real)
    _verify_area_location(area)
    if _is_link_like(raw):
        raise _refuse("要删除的路径本身是链接或联接", raw)
    is_root = len(_path_segments(real)) == len(area.segments)
    exists = os.path.lexists(real)

    if area.state == "removed":
        if exists:
            raise _refuse("所在的临时区域已被删除，新出现的路径无法核对归属", real)
        return
    if area.state == "marker_removed":
        # 上一次尝试已删完内容与标记、只差根目录本身（例如根目录被短暂占用）。只允许 os.rmdir 空目录（非递归）。
        if not os.path.lexists(area.root):
            area.state = "removed"
            if exists:
                raise _refuse("所在的临时区域已被删除，新出现的路径无法核对归属", real)
            return
        _verify_area_root(area)
        if not is_root:
            if exists:
                raise _refuse("临时区域的标记已删除，区域内新出现的路径无法核对归属", real)
            return
        os.rmdir(area.root)  # 非空时抛 OSError：不在不确定时递归删除
        area.state = "removed"
        return

    _verify_area(area)
    if not exists:
        return
    if not is_root:
        _rmtree(real)
        return
    # 删除区域本身：先删除标记以外的全部内容，最后删标记与根目录。中途失败时标记仍在，重试会重新完整核对。
    for name in os.listdir(area.root):
        if name != OWNER_MARKER_NAME:
            _remove_entry(os.path.join(area.root, name))
    leftover = [name for name in os.listdir(area.root) if name != OWNER_MARKER_NAME]
    if leftover:  # 删除期间又有东西写进来（例如尚未结束的子进程）：交给重试，重试前仍会重新核对
        raise OSError("临时区域在删除期间出现新条目：%s（%d 个）" % (area.root, len(leftover)))
    _verify_area_marker(area)
    os.unlink(os.path.join(area.root, OWNER_MARKER_NAME))
    area.state = "marker_removed"
    os.rmdir(area.root)
    area.state = "removed"


def remove_tree(path: Union[str, Path], retries: int = 5) -> None:
    """tests/test_dispatch.py:94-100：删除目录，只读文件（Windows 上的 git 对象）先改权限再删。

    与原函数不同：
    - 删除前核对归属（01 文档 8.4）。path 必须是本进程 make_temp_area() 建立的临时区域本身或其中的路径，且该区域
      同时满足：真实路径是 realpath(tempfile.gettempdir()) 的直接子目录（按路径分段比较，不做大小写折叠）、目录名以
      TEMP_AREA_PREFIX 开头、真实路径与目录身份与创建时相同、根目录中的所有权标记存在且内容与本进程创建时记录的
      随机值一致；path 本身不能是链接或联接，其真实路径（解析各级链接后）也必须落在该区域内。任一项不成立时抛
      CleanupOwnershipError，不删除任何东西，也不重试。
    - path 不存在时直接返回（同原函数），但归属核对照常进行：区域外的路径即使不存在也会被拒绝。
    - 删除区域本身时最后才删除标记文件，中途失败时标记仍在；每次重试之前都重新核对。
    - Windows 上文件可能被刚结束的进程或杀毒软件短暂占用：OSError 时最多重试 retries 次（间隔递增），仍失败则抛出
      最后一次异常（不吞掉）。
    """
    for attempt in range(retries + 1):
        try:
            _remove_owned_once(path)
            return
        except CleanupOwnershipError:
            raise
        except OSError:
            if attempt >= retries:
                raise
            time.sleep(0.2 * (attempt + 1))


def find_bash(env: Optional[Mapping[str, str]] = None) -> Optional[str]:
    """定位 Git Bash（Windows）或 bash（POSIX）；不会返回 System32/WindowsApps 下的 WSL 启动器。

    Windows 顺序：C:\\Program Files\\Git\\bin\\bash.exe（同 tests/test_dispatch.py:710）→ PATH 上 git.exe 所在
    Git 安装目录的 bin\\bash.exe → PATH 上的 bash（排除 WSL 启动器）。
    """
    path_value = _env_get(env, "PATH") if env is not None else None
    if IS_WINDOWS:
        fixed = Path(r"C:\Program Files\Git\bin\bash.exe")
        if fixed.is_file():
            return str(fixed)
        git = shutil.which("git", path=path_value)
        if git:
            for candidate in (Path(git).parent.parent / "bin" / "bash.exe",
                              Path(git).parent.parent.parent / "bin" / "bash.exe"):
                if candidate.is_file():
                    return str(candidate)
        found = shutil.which("bash", path=path_value)
        if found and not any(part in os.path.normcase(found) for part in ("\\system32\\", "\\windowsapps\\")):
            return found
        return None
    return shutil.which("bash", path=path_value)


def send_interrupt(proc: subprocess.Popen) -> None:
    """向进程发送“Ctrl+C”类中断：Windows 为 CTRL_BREAK_EVENT（旧实现登记了 SIGBREAK），要求目标以
    popen_tool(new_process_group=True) 启动；POSIX 为 SIGINT。失败时原样抛出（例如当前进程没有控制台）。"""
    if IS_WINDOWS:
        proc.send_signal(signal.CTRL_BREAK_EVENT)  # type: ignore[attr-defined]
    else:
        proc.send_signal(signal.SIGINT)


def wait_for(predicate: Callable[[], Any], timeout: float = 30.0, interval: float = 0.2) -> bool:
    """轮询 predicate 直到为真或超时；返回最后一次结果的真值（对应 tests/test_dispatch.py:463-466 的轮询）。"""
    deadline = time.monotonic() + timeout
    while True:
        if predicate():
            return True
        if time.monotonic() >= deadline:
            return bool(predicate())
        time.sleep(interval)


def _decode(data: Optional[bytes]) -> str:
    return (data or b"").decode("utf-8", "replace")


# ---------------------------------------------------------------------------
# unittest 基类
# ---------------------------------------------------------------------------

class LegacyCase(unittest.TestCase):
    """特征化测试基类：每个用例一个临时区域与受控环境。

    setUp 之后可用的属性：
      self.kit        被测源码目录（kit_dir()）
      self.work       本用例的临时区域（已 resolve）
      self.agent_dir  PI_CODING_AGENT_DIR 指向的空目录
      self.stub_cmd   [sys.executable, <stub_pi.py>]（默认的 PI_DISPATCH_PI_CMD）
      self.env        受控环境（所有子进程都由它派生）
      self.isolation  isolated_env 的 report（只含变量名与计数）
    """

    TOOL_TIMEOUT: float = DEFAULT_TOOL_TIMEOUT
    ISOLATE_GIT_GLOBAL: bool = True

    def setUp(self) -> None:
        super().setUp()
        self.kit = kit_dir()
        self.work = make_temp_area()  # mkdtemp(prefix=TEMP_AREA_PREFIX) 的真实路径，含所有权标记（8.4）
        self._procs: List[subprocess.Popen] = []
        self._pids: List[int] = []
        self._repos: List[Path] = []
        self._fake_count = 0
        self.addCleanup(self._cleanup_work)
        self.agent_dir = self.work / "pi-agent-empty"
        self.agent_dir.mkdir()
        git_global = None
        if self.ISOLATE_GIT_GLOBAL:
            git_global = self.work / "gitconfig-global-empty"
            git_global.write_bytes(b"")
        self.stub_cmd = [PY, str(stub_pi_path(self.kit))]
        self.env, self.isolation = isolated_env(self.stub_cmd, self.agent_dir, git_global,
                                                allowed_roots=[self.work])

    # -- 清理 ---------------------------------------------------------------

    def _cleanup_work(self) -> None:
        """对应 tests/test_dispatch.py:1922-1928：结束登记的进程 → git worktree prune → 删除临时区域。

        删除经 remove_tree，先核对归属（8.4）；核对不成立时抛 CleanupOwnershipError，用例报错并保留该目录。
        """
        for proc in self._procs:
            kill_tree(proc)
            for stream in (proc.stdout, proc.stderr, proc.stdin):
                if stream is not None:
                    stream.close()
        for pid in self._pids:
            if alive(pid):
                kill_hard(pid)
        env = getattr(self, "env", None)  # setUp 在建立受控环境之前失败时没有 env，也不会有仓库
        repos = set(self._repos)
        if self.work.is_dir():
            repos.update(p for p in self.work.iterdir() if (p / ".git").exists())
        for repo in sorted(repos):
            if env is not None and (repo / ".git").exists():
                subprocess.run(["git", "worktree", "prune"], cwd=str(repo), env=env, stdin=subprocess.DEVNULL,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
        remove_tree(self.work)

    def track_pid(self, pid: Union[int, str]) -> int:
        """登记一个需要在清理时结束的进程号（例如假 pi 的孙进程）；返回 int(pid)。"""
        value = int(pid)
        self._pids.append(value)
        return value

    # -- 环境与子进程 ---------------------------------------------------------

    def child_env(self, extra: Optional[Mapping[str, Optional[str]]] = None,
                  pi_cmd: Optional[Sequence[str]] = None) -> Dict[str, str]:
        """受控环境 + 测试显式传入的变量（值为 None 表示删除）；pi_cmd 覆盖 PI_DISPATCH_PI_CMD。

        对应 tests/test_dispatch.py:55-58 中 ``merged = dict(BASE_ENV); merged.update(env)``。启动前复核隔离。
        """
        merged = dict(self.env)
        if pi_cmd is not None:
            _env_set(merged, "PI_DISPATCH_PI_CMD", json.dumps([str(x) for x in pi_cmd]))
        for name, value in (extra or {}).items():
            _env_set(merged, name, None if value is None else str(value))
        assert_isolated(merged, [self.work], check_names=False)
        return merged

    def _run(self, cmd: Sequence[str], cwd: Union[str, Path], env: Mapping[str, str],
             timeout: Optional[float], merge: bool) -> Tuple[int, bytes, bytes]:
        proc = subprocess.Popen([str(c) for c in cmd], cwd=str(cwd), env=dict(env), stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT if merge else subprocess.PIPE)
        limit = self.TOOL_TIMEOUT if timeout is None else timeout
        try:
            out, err = proc.communicate(timeout=limit)
        except subprocess.TimeoutExpired:
            kill_tree(proc)
            out, err = proc.communicate(timeout=60)
            raise AssertionError("命令超时（%.0fs），已结束进程树：%s\n%s%s"
                                 % (limit, list(cmd), _decode(out)[-3000:], _decode(err)[-3000:]))
        return proc.returncode, out or b"", err or b""

    def sh(self, cmd: Sequence[str], cwd: Union[str, Path], env: Optional[Mapping[str, str]] = None,
           check: bool = True, timeout: Optional[float] = None) -> Tuple[int, str]:
        """tests/test_dispatch.py:43-48：运行命令，stdout 与 stderr 合并；check 时非 0 抛 AssertionError。"""
        run_env = self.env if env is None else env
        assert_isolated(run_env, [self.work], check_names=False)
        code, out, _ = self._run(cmd, cwd, run_env, timeout, merge=True)
        text = _decode(out)
        if check and code != 0:
            raise AssertionError("command failed %s -> %s\n%s" % (list(cmd), code, text))
        return code, text

    def git(self, repo: Union[str, Path], *args: str) -> str:
        """tests/test_dispatch.py:51-52：运行 git，失败抛错，返回去掉首尾空白的输出。"""
        return self.sh(["git"] + list(args), repo)[1].strip()

    def tool(self, repo: Union[str, Path], *args: str, env: Optional[Mapping[str, Optional[str]]] = None,
             pi_cmd: Optional[Sequence[str]] = None, cwd: Optional[Union[str, Path]] = None,
             timeout: Optional[float] = None) -> Tuple[int, str]:
        """tests/test_dispatch.py:55-58：在 cwd（默认 repo）运行 ``python scripts/pi_dispatch.py <args>``。

        返回 (退出码, stdout+stderr 合并文本)；非 0 不抛错。脚本路径相对 cwd（即临时仓库中由 make_repo 复制的副本）。
        """
        merged = self.child_env(env, pi_cmd)
        code, out, _ = self._run([PY, "scripts/pi_dispatch.py"] + list(args), cwd or repo, merged, timeout, True)
        return code, _decode(out)

    def tool_split(self, repo: Union[str, Path], *args: str, env: Optional[Mapping[str, Optional[str]]] = None,
                   pi_cmd: Optional[Sequence[str]] = None, cwd: Optional[Union[str, Path]] = None,
                   timeout: Optional[float] = None) -> Tuple[int, str, str]:
        """同 tool，但 stdout 与 stderr 分开返回：(退出码, stdout, stderr)。"""
        merged = self.child_env(env, pi_cmd)
        code, out, err = self._run([PY, "scripts/pi_dispatch.py"] + list(args), cwd or repo, merged, timeout, False)
        return code, _decode(out), _decode(err)

    def wrapper(self, repo: Union[str, Path], *args: str, env: Optional[Mapping[str, Optional[str]]] = None,
                pi_cmd: Optional[Sequence[str]] = None, timeout: Optional[float] = None) -> Tuple[int, str]:
        """经 ``bash scripts/dispatch-pi.sh <args>`` 运行（包装脚本按 PATH 找 python3/python/py）。

        找不到 bash 时抛 RuntimeError（环境缺失不静默跳过；需要按平台跳过的测试先自行调用 find_bash()）。
        """
        merged = self.child_env(env, pi_cmd)
        bash = find_bash(merged)
        if not bash:
            raise RuntimeError("找不到 bash（Windows 上为 Git Bash）")
        code, out, _ = self._run([bash, "scripts/dispatch-pi.sh"] + list(args), repo, merged, timeout, True)
        return code, _decode(out)

    def popen_tool(self, repo: Union[str, Path], *args: str, env: Optional[Mapping[str, Optional[str]]] = None,
                   pi_cmd: Optional[Sequence[str]] = None, new_process_group: bool = False,
                   stdout: Any = subprocess.PIPE, stderr: Any = subprocess.STDOUT) -> subprocess.Popen:
        """后台启动 ``python scripts/pi_dispatch.py <args>``（并发、取消、调度器被杀等场景）。

        对应 tests/test_dispatch.py:336-337、447-448 的 Popen。进程登记后在清理时结束；读取输出用
        proc.communicate()。new_process_group=True：Windows 加 CREATE_NEW_PROCESS_GROUP（send_interrupt 需要），
        POSIX 为 start_new_session。
        """
        merged = self.child_env(env, pi_cmd)
        kwargs: Dict[str, Any] = {}
        if new_process_group:
            if IS_WINDOWS:
                kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200)
            else:
                kwargs["start_new_session"] = True
        proc = subprocess.Popen([PY, "scripts/pi_dispatch.py"] + list(args), cwd=str(repo), env=merged,
                                stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr, **kwargs)
        self._procs.append(proc)
        return proc

    def wait_for(self, predicate: Callable[[], Any], timeout: float = 30.0, interval: float = 0.2) -> bool:
        return wait_for(predicate, timeout, interval)

    # -- 假 pi ----------------------------------------------------------------

    def fake_pi(self, events_lines: Iterable[EventLine], exit_code: int = 0, **kwargs: Any) -> List[str]:
        """在本用例临时区域生成假 pi（参数同 make_fake_pi），返回 argv；传给 tool(..., pi_cmd=argv)。"""
        self._fake_count += 1
        directory = self.work / ("fake-pi-%02d" % self._fake_count)
        kwargs.setdefault("kit", self.kit)
        return make_fake_pi(directory, events_lines, exit_code, **kwargs)

    # -- 临时仓库与合同 ---------------------------------------------------------

    contract = staticmethod(contract)
    build_md = staticmethod(build_md)
    jload = staticmethod(jload)

    def write_config(self, repo: Path, **extra: Any) -> None:
        """tests/test_dispatch.py:162-166：写 .agent/dispatch.config.json（worktree_root 在本用例临时区域）。"""
        config: Dict[str, Any] = {"worktree_root": str(self.work / "worktrees")}
        config.update(extra)
        (repo / ".agent").mkdir(exist_ok=True)
        (repo / ".agent/dispatch.config.json").write_text(json.dumps(config), encoding="utf-8")

    def make_repo(self, name: str = "repo", attempts: int = 3, thinking: str = "high",
                  gitignore: str = DEFAULT_GITIGNORE, **over: Any) -> Tuple[Path, str]:
        """tests/test_dispatch.py:169-196：建临时 Git 仓库并提交 base，返回 (repo, base_sha)。

        与原函数一致：提交 base 之后才写 .agent/dispatch.config.json 与 normalize-query.v1.{md,json}，
        所以它们在主仓库中是未跟踪文件；脚本从 KIT 复制。over 覆盖合同顶层键。
        """
        repo = self.work / name
        remove_tree(repo)
        for sub in ("src", "tests", "scripts"):
            (repo / sub).mkdir(parents=True)
        self._repos.append(repo)
        self.sh(["git", "init", "-q"], repo)
        self.git(repo, "config", "user.email", "t@example.invalid")
        self.git(repo, "config", "user.name", "tester")
        self.git(repo, "config", "core.autocrlf", "false")
        self.git(repo, "config", "commit.gpgsign", "false")
        (repo / "src/normalize.py").write_text("def normalize(q):\n    return q\n", encoding="utf-8")
        (repo / "run_tests.py").write_text(
            "import sys, unittest\nsys.path.insert(0, 'src')\n"
            "r = unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.discover('tests'))\n"
            "ok = r.wasSuccessful() and r.testsRun > 0\n"
            "print('Tests %d passed' % r.testsRun if ok else 'FAILED')\nsys.exit(0 if ok else 1)\n", encoding="utf-8")
        (repo / "README.md").write_text("# Test\n", encoding="utf-8")
        (repo / "package.json").write_text('{"name":"t","dependencies":{}}\n', encoding="utf-8")
        (repo / ".gitignore").write_text(gitignore, encoding="utf-8")
        (repo / "AGENTS.md").write_text("# AGENTS\n只改合同允许的文件。\n", encoding="utf-8")
        for script in ("pi_dispatch.py", "dispatch-pi.sh"):
            shutil.copy(str(self.kit / "scripts" / script), str(repo / "scripts" / script))
        self.git(repo, "add", "-A")
        self.git(repo, "commit", "-qm", "base")
        base = self.git(repo, "rev-parse", "HEAD")
        self.write_config(repo)
        self.write_plan(repo, base, 1, attempts, thinking, **over)
        return repo, base

    def write_plan(self, repo: Path, base: str, ver: int, attempts: int = 3, thinking: str = "high",
                   md: Optional[str] = None, raw: Any = None, **over: Any) -> Dict[str, Any]:
        """tests/test_dispatch.py:199-205：写 .agent/plans/normalize-query.v<ver>.{md,json}。

        md 给定时代替 build_md 的结果；raw 给定时代替合同 JSON（任意 JSON 值）。返回 contract(...) 生成的数据。
        """
        plans = repo / ".agent/plans"
        plans.mkdir(parents=True, exist_ok=True)
        data = contract(base, ver, attempts, thinking, **over)
        (plans / ("normalize-query.v%d.md" % ver)).write_text(md if md is not None else build_md(data),
                                                             encoding="utf-8")
        (plans / ("normalize-query.v%d.json" % ver)).write_text(
            json.dumps(raw if raw is not None else data, ensure_ascii=False, indent=2), encoding="utf-8")
        return data

    def write_plan_raw(self, repo: Path, plan_key: str, md: Optional[Union[str, bytes]],
                       json_: Optional[Union[str, bytes, Any]]) -> None:
        """按原字节写合同文件（新增，test_dispatch 没有）：bytes 原样写；str 按 UTF-8 编码、不做换行转换；
        其他值 json.dumps(ensure_ascii=False, indent=2)；None 表示不写该文件（用于“缺少文件”）。"""
        plans = repo / ".agent/plans"
        plans.mkdir(parents=True, exist_ok=True)
        for suffix, value in ((".md", md), (".json", json_)):
            if value is None:
                continue
            if isinstance(value, bytes):
                data = value
            elif isinstance(value, str):
                data = value.encode("utf-8")
            else:
                data = json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")
            (plans / (plan_key + suffix)).write_bytes(data)

    # -- attempt 与证据 --------------------------------------------------------

    @staticmethod
    def attempt_ref(n: int = 1, task_id: str = TASK_ID) -> str:
        """子命令使用的 attempt 标识，例如 normalize-query/attempt-001。"""
        return "%s/attempt-%03d" % (task_id, n)

    def rd(self, repo: Path, n: int = 1, task_id: str = TASK_ID) -> Path:
        """tests/test_dispatch.py:208-209：attempt 运行目录。"""
        return repo / (".agent/runs/%s/attempt-%03d" % (task_id, n))

    def state_record(self, repo: Path, n: int = 1, task_id: str = TASK_ID) -> Dict[str, Any]:
        """state.json 的完整内容。"""
        return jload(self.rd(repo, n, task_id) / "state.json")

    def state(self, repo: Path, n: int = 1, task_id: str = TASK_ID) -> str:
        """tests/test_dispatch.py:212-213：state.json 的 state 字段。"""
        return self.state_record(repo, n, task_id)["state"]

    def review(self, repo: Path, verdict: str, name: str = "r.md", text: Optional[str] = None) -> str:
        """tests/test_dispatch.py:220-224：写 .agent/reviews/<name>（默认内容含 ``Verdict: <verdict>``），返回路径。"""
        path = repo / ".agent/reviews" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text if text is not None else "# REVIEW\n\nVerdict: %s\n" % verdict, encoding="utf-8")
        return str(path)

    def worktree_of(self, repo: Path, n: int = 1, task_id: str = TASK_ID) -> Path:
        """tests/test_dispatch.py:227-228：meta.json 记录的 worktree。"""
        return Path(jload(self.rd(repo, n, task_id) / "meta.json")["worktree"])

    def run_ok(self, repo: Path, n: int = 1, plan_key: str = PLAN_KEY, pi_cmd: Optional[Sequence[str]] = None,
               **env: str) -> Tuple[int, str]:
        """tests/test_dispatch.py:231-234：prepare（断言退出 0）后 run attempt n，STUB_SCENARIO 默认 ok。"""
        code, out = self.tool(repo, "prepare", plan_key)
        self.assertEqual(code, 0, "prepare 失败：\n" + out)
        env.setdefault("STUB_SCENARIO", "ok")
        return self.tool(repo, "run", self.attempt_ref(n), env=env, pi_cmd=pi_cmd)

    # -- 旧实现模块 -------------------------------------------------------------

    @property
    def pd(self) -> types.ModuleType:
        """进程内加载的 KIT/scripts/pi_dispatch.py（EXIT_* 常量、set_state 等）；见 load_legacy_module。"""
        return load_legacy_module(self.kit)
