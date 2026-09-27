#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""codekit baseline —— 01-T1 基线取证工具（01 文档 2.2、2.4、6.2、6.3、6.4、8.4）。

用法：
  python scripts/codekit/baseline.py capture --out-root <dir> [--capture-id ID] [--timeout SEC]
         [--grace SEC] [--exclude <repo-relative-prefix> ...] -- <argv...>
  python scripts/codekit/baseline.py archive <capture-dir> --dest <dir>

capture：前采样（pre/）→ 在现有监督器 pi_dispatch.run_supervised 中运行被测命令（run/）→ 后采样（post/）
→ 比较前后采样 → 写 capture.json。所有输出以 "xb" 独占创建，已存在即失败，不覆盖。
archive：校验 capture 文件摘要后复制到 <dest>/<capture-id>/，对可按 UTF-8 解码的文件做版本化脱敏，
写 archive-manifest.json。

退出码：0 = 取证/归档完整（不解释被测命令是否通过，退出码 0 不是通过的充分条件）；
        1 = 取证不完整或出错（已写出的记录保留，不删除）；2 = 用法错误。

--out-root 与 --dest 的相对路径按仓库根（git rev-parse --show-toplevel）解析；
archive 的 <capture-dir> 相对路径按当前目录解析。

导入本模块不运行命令、不写文件、不导入调度器：scripts/pi_dispatch.py 只在执行子命令时
按“先读字节、算摘要、再编译这份字节”的方式加载，不写 __pycache__。只依赖标准库。
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as _dt
import hashlib
import json
import os
import platform
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import types
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

TOOL_NAME = "codekit-baseline"
CAPTURE_SCHEMA_VERSION = 1
EXIT_OK, EXIT_INCOMPLETE, EXIT_USAGE = 0, 1, 2

DEFAULT_TIMEOUT = 3600.0
#: 与 pi_dispatch.run_supervised 的默认宽限相同：超时后先请求结束，宽限期过后结束整个进程树。
DEFAULT_GRACE = 15.0
DEFAULT_EXCLUDES = (".agent/baseline/",)
#: 采样用的 git/bash 短命令各自的时限（秒）；超时记为 reason=timeout，取证不完整。
SAMPLE_COMMAND_TIMEOUT = 300.0

REDACTION_RULE_REVISION = "redact-v2"  # v2：疑似 UTF-16 的文本按 UTF-16 解码后脱敏
#: 同一段文字同时属于多个类别时的优先级：更具体的类别在前。
REDACTION_CATEGORIES = ("<REPO>", "<TEMP>", "<PYDIR>", "<HOME>")

CONFIG_KEYS = ("core.autocrlf", "core.eol", "core.fsmonitor", "core.symlinks", "core.filemode",
               "core.ignorecase", "core.longpaths", "core.safecrlf")
ENV_NAME_ALLOWLIST = ("PI_DISPATCH_PI_CMD", "PI_EXEC_PROVIDER", "PI_EXEC_MODEL", "PI_EXEC_THINKING",
                      "STUB_SCENARIO", "PYTHONPATH", "PYTHONHOME", "PYTHONDONTWRITEBYTECODE",
                      "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "PI_CODING_AGENT_DIR",
                      "PI_DISPATCH_WORKTREE_ROOT")
#: 只用 shutil.which 定位、从不执行的外部命令；用来证明取证环境是否把它们隔离在 PATH 之外。
LOCATED_COMMANDS = ("git", "bash", "pi", "claude", "codex", "node")
#: git rev-parse --show-object-format 的已知取值；旧版 Git 会把不认识的选项原样回显并返回 0。
KNOWN_OBJECT_FORMATS = {"sha1": 40, "sha256": 64}
PYTHON_STARTUP_VARS = ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP")
GIT_REDIRECT_NAMES = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")

CAPTURE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
OID_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL"} | {"COM%d" % i for i in range(10)} | {"LPT%d" % i for i in range(10)}
_PORCELAIN_STATUS_BYTES = frozenset(b" MTADRCU?!")
_SYS_FLAGS_SKIP = ("count", "index", "n_fields", "n_sequence_fields", "n_unnamed_fields")

STATIC_LIMITATIONS = (
    "输入清单按采样时刻的工作区字节计算摘要；不证明被测命令实际读取的就是这些字节（读取与使用之间的竞态未消除，文档 4.1.6）。",
    "被 .gitignore 忽略的文件只列名称与数量，不计算摘要，未纳入输入闭包：忽略项名称的增减会改变输入清单摘要并计入漂移，"
    "但已存在的忽略文件内容变化（例如 .env 被改写）无法发现。",
    "--exclude 同时作用于输入清单条目与忽略项名称；被排除路径的数量只记录在 capture.json 的 exclusion_counts 中，"
    "其变化作为观察记录，不计入漂移（其状态变化仍可能体现在 porcelain 原始字节中）。",
    "子模块与嵌套仓库的内容未展开；仓库外输入（依赖包、全局/系统 Git 配置文件、解释器标准库、系统工具）未纳入输入闭包。",
    "只记录选定的 core.* Git 配置；未解析 .gitattributes、过滤器与 textconv 的实际效果（差异采集时已禁用 ext-diff/textconv）。",
    "Python 启动事实描述的是运行本工具的解释器，被测命令可能使用另一个解释器。",
    "被测命令的 argv[0] 由操作系统解析：Windows 的 CreateProcess 会先查找父进程程序目录与当前目录，结果可能与 argv0_which（shutil.which）不同。",
    "git/bash 采样命令用 shutil.which 解析出的绝对路径执行；Windows 上 shutil.which 会先查当前目录。",
    "本工具不提供网络隔离、凭据隔离或沙箱；被测命令以调用者的操作系统账户运行。",
    "前后采样不是原子快照：采样期间的并发修改可能只被部分观察到。",
    "工具自身摘要是启动时读取的 baseline.py 字节；监督器摘要是实际编译执行的 pi_dispatch.py 字节。",
)


# ---------------------------------------------------------------------------
# 通用工具（纯函数或只在调用时读文件）
# ---------------------------------------------------------------------------

def utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def canonical_json_bytes(obj: Any) -> bytes:
    """01 文档 4.2.6 的固定序列化：UTF-8、无 BOM、末尾一个 LF。"""
    text = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return (text + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> Tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def safe_text(text: str) -> str:
    """去掉无法编码为 UTF-8 的代理字符，保证记录可以固定序列化。"""
    return text.encode("utf-8", "backslashreplace").decode("utf-8")


def exc_text(exc: BaseException) -> str:
    return safe_text("%s: %s" % (type(exc).__name__, exc))


def decode_git_path(raw: bytes) -> Tuple[str, bool]:
    """Git 输出的路径是原始字节；严格按 UTF-8 解码，失败时返回转义文本并标记。"""
    try:
        return raw.decode("utf-8"), True
    except UnicodeDecodeError:
        return raw.decode("utf-8", "backslashreplace"), False


def parse_porcelain_v1_z(data: bytes) -> List[Dict[str, Any]]:
    """解析 `git status --porcelain=v1 -z`。

    每条记录为 ``XY<空格>PATH\\0``；X 或 Y 为 R/C（重命名/复制）时，后面紧跟一个额外的 ``ORIG_PATH\\0``
    （-z 格式中先新路径、后原路径）。路径不加引号、不转义，可能含空格、换行与非 ASCII 字符，所以不能按行切分。
    格式不符时抛出 ValueError，不猜测。
    """
    entries: List[Dict[str, Any]] = []
    i, n = 0, len(data)
    while i < n:
        if n - i < 5:
            raise ValueError("porcelain 记录在偏移 %d 处被截断" % i)
        x, y, sep = data[i], data[i + 1], data[i + 2]
        if x not in _PORCELAIN_STATUS_BYTES or y not in _PORCELAIN_STATUS_BYTES or sep != 0x20:
            raise ValueError("偏移 %d 处不是合法的 porcelain v1 状态字段" % i)
        end = data.find(b"\0", i + 3)
        if end == -1:
            raise ValueError("偏移 %d 处的路径缺少 NUL 结尾" % i)
        raw_path = data[i + 3:end]
        if not raw_path:
            raise ValueError("偏移 %d 处的路径为空" % i)
        i = end + 1
        xy = chr(x) + chr(y)
        raw_orig: Optional[bytes] = None
        if chr(x) in "RC" or chr(y) in "RC":
            end2 = data.find(b"\0", i)
            if end2 == -1 or end2 == i:
                raise ValueError("重命名/复制记录 %r 缺少原路径" % xy)
            raw_orig = data[i:end2]
            i = end2 + 1
        path, path_ok = decode_git_path(raw_path)
        entry: Dict[str, Any] = {"xy": xy, "path": path, "path_utf8": path_ok, "orig_path": None}
        if raw_orig is not None:
            orig, orig_ok = decode_git_path(raw_orig)
            entry["orig_path"] = orig
            entry["path_utf8"] = path_ok and orig_ok
        entries.append(entry)
    return entries


def parse_nul_list(data: bytes) -> List[bytes]:
    """解析以 NUL 结尾的列表（如 ls-files -z）。"""
    if not data:
        return []
    if not data.endswith(b"\0"):
        raise ValueError("NUL 分隔列表缺少末尾 NUL")
    return data[:-1].split(b"\0")


def validate_exclude(entry: str) -> Optional[str]:
    """返回错误说明；合法时返回 None。排除项必须是仓库相对、正斜杠、无歧义分段的精确前缀。"""
    if not entry:
        return "排除项为空"
    if any(ord(ch) < 0x20 or ch == "\x7f" for ch in entry):
        return "排除项含控制字符"
    if "\\" in entry:
        return "排除项必须用正斜杠"
    if entry.startswith("/") or re.match(r"^[A-Za-z]:", entry):
        return "排除项必须是仓库相对路径"
    segments = entry[:-1].split("/") if entry.endswith("/") else entry.split("/")
    for segment in segments:
        if segment in ("", ".", ".."):
            return "排除项含空分段、. 或 .."
    return None


def match_exclusion(path: str, rules: Sequence[str]) -> Optional[str]:
    """以 / 结尾的规则按字面前缀匹配（out/ 不匹配 outx/）；否则只匹配完全相同的路径。"""
    for rule in rules:
        if rule.endswith("/"):
            if path.startswith(rule):
                return rule
        elif path == rule:
            return rule
    return None


def validate_capture_id(value: str) -> Optional[str]:
    if not CAPTURE_ID_RE.fullmatch(value):
        return "capture-id 只能由字母、数字、. _ - 组成，以字母或数字开头，最长 128 个字符"
    if value.endswith("."):
        return "capture-id 不能以 . 结尾"
    if value.split(".")[0].upper() in _WINDOWS_RESERVED:
        return "capture-id 不能是 Windows 保留设备名"
    return None


def default_capture_id() -> str:
    return "bl-%s-%s" % (_dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"), secrets.token_hex(4))


_WINDOWS_VERBATIM_UNC_PREFIX = "\\\\?\\UNC\\"
_WINDOWS_VERBATIM_PREFIX = "\\\\?\\"


def real_parts(path: str) -> Tuple[str, ...]:
    """realpath 后的路径分段（逐字，不折叠大小写）。

    Windows 上去掉 realpath 在超长路径上可能保留的 \\\\?\\ 前缀，使同一路径的两种写法得到相同分段。
    """
    text = os.path.realpath(path)
    if os.name == "nt":
        if text.startswith(_WINDOWS_VERBATIM_UNC_PREFIX):
            text = "\\\\" + text[len(_WINDOWS_VERBATIM_UNC_PREFIX):]
        elif text.startswith(_WINDOWS_VERBATIM_PREFIX):
            text = text[len(_WINDOWS_VERBATIM_PREFIX):]
    return Path(text).parts


def relative_within(child: str, parent: str) -> Optional[str]:
    """child 位于 parent 之内（含 parent 本身）时返回以 / 分隔的相对路径（parent 本身为 "."），否则 None。

    两边都先 realpath，再要求 parent 的分段是 child 分段的**逐字**前缀。Windows 上 realpath 经
    GetFinalPathNameByHandle 给出磁盘上的真实拼写（大小写、8.3 短名、符号链接与 junction 都已规范化；
    尚不存在的尾部保留原拼写），所以同一目录的不同写法得到相同分段。

    不用 os.path.normcase / os.path.commonpath：normcase 按区域无关规则折叠大小写（缺少
    LCMapStringEx 的实现退化为 str.lower()），ntpath.commonpath 内部也用 str.lower() 比较；而 NTFS
    的名称等价规则与之不同——开启了按目录大小写敏感的目录中 Repo 与 repo 是两个目录，K 与 U+212A
    （开尔文符号）在 str.lower() 后相同、在 NTFS 上却是两个名称。按折叠后比较会把这类根外的兄弟目录
    当成根内。拼写不同一律视为不在根内（与 protocols._is_within 一致）。

    调用方要求 parent 已存在：它的写法会被规范化，child 中已存在的前缀也会，所以“归档目标不得位于
    取证目录内”这类以“在内”为拒绝条件的检查，不会因 ASCII 大小写、8.3 短名、/ 分隔或链接写法而漏判。
    """
    child_parts, parent_parts = real_parts(child), real_parts(parent)
    if len(child_parts) < len(parent_parts) or child_parts[:len(parent_parts)] != parent_parts:
        return None
    return "/".join(child_parts[len(parent_parts):]) or "."


def is_within(child: str, parent: str) -> bool:
    """child 是否位于 parent 之内（含 parent 本身）；判定规则见 relative_within。"""
    return relative_within(child, parent) is not None


def load_supervisor() -> Tuple[types.ModuleType, Dict[str, Any]]:
    """加载同一仓库副本中的 scripts/pi_dispatch.py（经批准的现有监督器）。

    先读字节并计算摘要，再编译执行这同一份字节：记录的摘要就是实际使用的代码，也不写 __pycache__。
    """
    path = Path(__file__).resolve().parent.parent / "pi_dispatch.py"
    data = path.read_bytes()
    name = "_codekit_pi_dispatch"
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    try:
        exec(compile(data, str(path), "exec"), module.__dict__)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    info = {"module": "scripts/pi_dispatch.py", "function": "run_supervised", "module_sha256": sha256_bytes(data),
            "module_tool_version": getattr(module, "TOOL_VERSION", None)}
    return module, info


def tool_self_info(repo_root: Optional[Path]) -> Dict[str, Any]:
    path = Path(__file__).resolve()
    rel = relative_within(str(path), str(repo_root)) if repo_root is not None else None
    return {"name": TOOL_NAME, "path": rel, "sha256": sha256_bytes(path.read_bytes())}


def git_toplevel(env: Dict[str, str], cwd: Optional[Path] = None) -> Tuple[Optional[Path], str]:
    try:
        proc = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=str(cwd) if cwd else None, env=env,
                              stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=SAMPLE_COMMAND_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, exc_text(exc)
    if proc.returncode != 0:
        return None, safe_text(proc.stderr.decode("utf-8", "replace").strip())
    text = proc.stdout.decode("utf-8", "replace").strip()
    return (Path(text), "") if text else (None, "git rev-parse --show-toplevel 没有输出")


# ---------------------------------------------------------------------------
# 取证上下文
# ---------------------------------------------------------------------------

class CaptureContext:
    def __init__(self, capture_dir: Path, repo_root: Path) -> None:
        self.capture_dir = capture_dir
        self.repo_root = repo_root
        self.files: List[Dict[str, Any]] = []

    def rel(self, path: Path) -> str:
        return os.path.relpath(str(path), str(self.capture_dir)).replace("\\", "/")

    def file_ref(self, path: Path) -> Dict[str, Any]:
        digest, size = sha256_file(path)
        ref = {"path": self.rel(path), "sha256": digest, "bytes": size}
        self.files.append(dict(ref))
        return ref

    def write_exclusive(self, path: Path, data: bytes) -> Dict[str, Any]:
        with open(path, "xb") as handle:
            handle.write(data)
        return self.file_ref(path)


def interpret_returncode(code: Optional[int]) -> Dict[str, Any]:
    if code is None:
        return {"returncode": None, "reason": "exit_status_unavailable"}
    if code < 0 and os.name != "nt":
        return {"returncode": None, "reason": "terminated_by_signal", "signal": -code}
    return {"returncode": code, "reason": None}


def run_to_files(ctx: CaptureContext, phase_dir: Path, cmd_id: str, argv: Sequence[str],
                 executable: Optional[str], env: Dict[str, str]) -> Dict[str, Any]:
    """采样用短命令：argv 列表、shell=False、stdin=DEVNULL，stdout/stderr 分别写入独占创建的二进制文件。"""
    record: Dict[str, Any] = {"id": cmd_id, "argv": list(argv), "executable": executable, "returncode": None,
                              "reason": None, "duration_seconds": None, "stdout": None, "stderr": None}
    if executable is None:
        record["reason"] = "executable_not_found"
        return record
    out_path = phase_dir / (cmd_id + ".stdout.bin")
    err_path = phase_dir / (cmd_id + ".stderr.bin")
    started = time.monotonic()
    try:
        with open(out_path, "xb") as out, open(err_path, "xb") as err:
            try:
                proc = subprocess.run([executable] + list(argv[1:]), cwd=str(ctx.repo_root), env=env,
                                      stdin=subprocess.DEVNULL, stdout=out, stderr=err, shell=False, check=False,
                                      timeout=SAMPLE_COMMAND_TIMEOUT)
                record.update(interpret_returncode(proc.returncode))
            except subprocess.TimeoutExpired:
                record["reason"] = "timeout"
            except OSError as exc:
                record["reason"] = "spawn_failed"
                record["error"] = exc_text(exc)
    except OSError as exc:
        record["reason"] = "output_write_failed"
        record["error"] = exc_text(exc)
    record["duration_seconds"] = round(time.monotonic() - started, 6)
    for key, path in (("stdout", out_path), ("stderr", err_path)):
        if path.exists():
            record[key] = ctx.file_ref(path)
    return record


def read_ref(ctx: CaptureContext, ref: Optional[Dict[str, Any]]) -> Optional[bytes]:
    if not ref:
        return None
    return (ctx.capture_dir / ref["path"]).read_bytes()


def first_line(data: Optional[bytes]) -> Optional[str]:
    if data is None:
        return None
    text = data.decode("utf-8", "replace").strip()
    return safe_text(text.splitlines()[0]) if text else None


def python_startup_facts() -> Dict[str, Any]:
    flags: Dict[str, Any] = {}
    for name in dir(sys.flags):
        if name.startswith("_") or name in _SYS_FLAGS_SKIP:
            continue
        value = getattr(sys.flags, name)
        if isinstance(value, (bool, int)):
            flags[name] = value
    return {
        "scope": "capturing_interpreter",
        "sys_flags": flags,
        "dont_write_bytecode": bool(sys.dont_write_bytecode),
        "in_virtual_environment": sys.prefix != getattr(sys, "base_prefix", sys.prefix),
        "env_vars_set": {name: name in os.environ for name in PYTHON_STARTUP_VARS},
        "note": "只记录是否设置，不记录值；描述运行本工具的解释器",
    }


def environment_facts() -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "record_type": "baseline-environment",
        "platform": {"system": platform.system(), "release": platform.release(), "version": platform.version(),
                     "machine": platform.machine()},
        "os_name": os.name,
        "python": {"version": sys.version, "version_info": list(sys.version_info),
                   "implementation": platform.python_implementation(), "executable": sys.executable},
        "which": {name: shutil.which(name) for name in LOCATED_COMMANDS},
        "env_names_present": {name: name in os.environ for name in ENV_NAME_ALLOWLIST},
        "notes": ["环境变量只记录是否存在，不记录值",
                  "which 中的命令只用 shutil.which 定位，均未执行",
                  "sys.executable 与 which 结果是机器定位，属于环境事实，不是业务路径"],
    }


def stat_item(repo_root: Path, path: str, path_ok: bool) -> Dict[str, Any]:
    result: Dict[str, Any] = {"type": "other", "size": None, "sha256": None, "hash_basis": None}
    if not path_ok:
        result["note"] = "path_not_utf8"
        return result
    if path.endswith("/"):
        result["note"] = "untracked_directory_entry"  # 常见于嵌套仓库；内容未展开
        return result
    fs_path = os.path.join(str(repo_root), *path.split("/"))
    try:
        st = os.lstat(fs_path)
    except (FileNotFoundError, NotADirectoryError):
        result["type"] = "missing"
        return result
    except OSError as exc:
        result["note"] = "read_error: metadata: %s" % exc_text(exc)
        return result
    try:
        if stat.S_ISLNK(st.st_mode):
            target = os.fsencode(os.readlink(fs_path))
            result.update({"type": "symlink", "size": len(target), "sha256": sha256_bytes(target),
                           "hash_basis": "link_target"})
            return result
        if not stat.S_ISREG(st.st_mode):
            result["note"] = "directory" if stat.S_ISDIR(st.st_mode) else "special_file"
            return result
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(fs_path, flags)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                result["note"] = "read_error: changed_type_while_opening"
                return result
            digest = hashlib.sha256()
            size = 0
            while True:
                chunk = os.read(fd, 1 << 20)
                if not chunk:
                    break
                digest.update(chunk)
                size += len(chunk)
        finally:
            os.close(fd)
    except OSError as exc:
        result.update({"type": "other", "size": None, "sha256": None, "hash_basis": None,
                       "note": "read_error: %s" % exc_text(exc)})
        return result
    result.update({"type": "file", "size": size, "sha256": digest.hexdigest(), "hash_basis": "worktree_bytes"})
    return result


def build_input_manifest(repo_root: Path, status_entries: List[Dict[str, Any]],
                         ignored_entries: List[Dict[str, Any]], tracked_raw: List[bytes],
                         excludes: Sequence[str]) -> Tuple[Dict[str, Any], Dict[str, Dict[str, int]]]:
    """返回 (输入清单, 各排除规则的计数)。

    计数不写入清单：被排除路径的增减不应改变清单摘要，否则会出现无法用逐项差异解释的漂移。
    """
    primary: Dict[str, Dict[str, Any]] = {}
    for entry in status_entries:
        if entry["xy"] != "??":
            primary.setdefault(entry["path"], entry)
    candidates: Dict[str, Dict[str, Any]] = {}
    duplicate_tracked = 0
    for raw in tracked_raw:
        path, ok = decode_git_path(raw)
        if path in candidates:
            duplicate_tracked += 1  # 未合并条目在 ls-files 中按 stage 重复出现
            continue
        candidates[path] = {"path": path, "source": "tracked", "path_utf8": ok}
    for entry in status_entries:
        if entry["xy"] == "??" and entry["path"] not in candidates:
            candidates[entry["path"]] = {"path": entry["path"], "source": "untracked", "path_utf8": entry["path_utf8"]}
    for entry in status_entries:
        if entry["xy"] in ("??", "!!"):
            continue
        for key in ("path", "orig_path"):
            value = entry.get(key)
            if value and value not in candidates:
                candidates[value] = {"path": value, "source": "status_only", "path_utf8": entry["path_utf8"]}
    rule_counts: Dict[str, Dict[str, int]] = {rule: {"inputs": 0, "ignored_names": 0} for rule in excludes}
    items: List[Dict[str, Any]] = []
    for path in sorted(candidates):
        cand = candidates[path]
        rule = match_exclusion(path, excludes)
        if rule is not None:
            rule_counts[rule]["inputs"] += 1
            continue
        status_entry = primary.get(path)
        item: Dict[str, Any] = {"path": path, "source": cand["source"],
                                "status_xy": "??" if cand["source"] == "untracked" else
                                (status_entry["xy"] if status_entry else None)}
        if status_entry and status_entry.get("orig_path"):
            item["rename_from"] = status_entry["orig_path"]
        if cand["source"] == "status_only":
            for entry in status_entries:
                if entry.get("orig_path") == path:
                    item["status_xy"] = entry["xy"]
                    item["role"] = "rename_or_copy_source"
                    break
        item.update(stat_item(repo_root, path, cand["path_utf8"]))
        if not cand["path_utf8"]:
            item["path_utf8"] = False
        items.append(item)
    ignored_names: List[str] = []
    for entry in ignored_entries:
        if entry["xy"] != "!!":
            continue
        rule = match_exclusion(entry["path"], excludes)
        if rule is not None:
            rule_counts[rule]["ignored_names"] += 1
            continue
        ignored_names.append(entry["path"])
    ignored_names.sort()
    gitmodules = os.path.join(str(repo_root), ".gitmodules")
    counts = {"tracked": 0, "untracked": 0, "status_only": 0}
    for item in items:
        counts[item["source"]] += 1
    counts["duplicate_tracked_entries"] = duplicate_tracked
    manifest = {
        "schema_version": 1,
        "record_type": "baseline-input-manifest",
        "serialization": "json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':'), "
                         "allow_nan=False) + LF, UTF-8",
        "closure_digest_rule": "closure_sha256 = sha256(本清单去掉 ignored 键后的同一固定序列化字节)",
        "items": items,
        "counts": counts,
        "exclusions": {
            "rules": [{"entry": rule, "match": "prefix" if rule.endswith("/") else "exact"} for rule in excludes],
            "semantics": "以 / 结尾的规则按字面前缀匹配（out/ 不匹配 outx/）；其他规则只匹配完全相同的路径",
            "applies_to": ["items", "ignored.names"],
            "counts_location": "各规则排除的路径数记录在 capture.json 对应采样的 exclusion_counts 中，不写入本清单，"
                               "被排除路径的增减不改变本清单摘要",
        },
        "ignored": {"closure": "not_included", "note": "未纳入输入闭包：只列名称与数量，不计算摘要",
                    "source": "git status --porcelain=v1 -z --ignored=matching --untracked-files=all",
                    "count": len(ignored_names), "names": ignored_names},
        "submodules": {"gitmodules_present": os.path.lexists(gitmodules),
                       "gitmodules_tracked": ".gitmodules" in candidates and candidates[".gitmodules"]["source"] == "tracked",
                       "tracked_non_file_paths": [i["path"] for i in items
                                                  if i["source"] == "tracked" and i["type"] == "other"],
                       "note": "子模块与嵌套仓库内容未展开"},
        "python_startup": python_startup_facts(),
        "closure_status": "partial",
        "closure_gaps": ["ignored_files_not_hashed", "submodule_contents_not_expanded",
                         "out_of_repo_inputs_not_included", "gitattributes_effects_not_evaluated"],
    }
    return manifest, rule_counts


def closure_sha256(manifest: Dict[str, Any]) -> str:
    return sha256_bytes(canonical_json_bytes({k: v for k, v in manifest.items() if k != "ignored"}))


def take_sample(ctx: CaptureContext, phase: str, env: Dict[str, str], excludes: Sequence[str],
                git_exe: Optional[str], bash_exe: Optional[str]) -> Dict[str, Any]:
    phase_dir = ctx.capture_dir / phase
    sample: Dict[str, Any] = {"phase": phase, "started_at": utc_now(), "finished_at": None, "commands": [],
                              "facts": {}, "problems": [], "complete": False, "input_manifest": None,
                              "exclusion_counts": None, "environment": None}
    problems: List[str] = sample["problems"]
    facts: Dict[str, Any] = sample["facts"]
    try:
        phase_dir.mkdir()
        outputs: Dict[str, Optional[bytes]] = {}

        def run(cmd_id: str, argv: List[str], exe: Optional[str], required: bool = True,
                ok_codes: Tuple[int, ...] = (0,)) -> Dict[str, Any]:
            record = run_to_files(ctx, phase_dir, cmd_id, argv, exe, env)
            sample["commands"].append(record)
            outputs[cmd_id] = read_ref(ctx, record["stdout"]) if record["returncode"] in ok_codes else None
            if required and record["returncode"] not in ok_codes:
                problems.append("%s 失败：returncode=%s reason=%s" % (cmd_id, record["returncode"], record["reason"]))
            return record

        run("01-git-version", ["git", "--version"], git_exe)
        facts["git_version"] = first_line(outputs["01-git-version"])
        run("02-rev-parse-toplevel", ["git", "rev-parse", "--show-toplevel"], git_exe)
        top = first_line(outputs["02-rev-parse-toplevel"])
        facts["toplevel_matches_repo_root"] = None if top is None else \
            real_parts(top) == real_parts(str(ctx.repo_root))  # 逐字比较分段，理由见 relative_within
        if facts["toplevel_matches_repo_root"] is False:
            problems.append("rev-parse --show-toplevel 与取证开始时的仓库根不一致")
        run("03-rev-parse-head", ["git", "rev-parse", "--verify", "--end-of-options", "HEAD^{commit}"], git_exe)
        head = first_line(outputs["03-rev-parse-head"])
        if head is not None and not OID_RE.match(head):
            problems.append("HEAD 输出不是完整 OID")
            head = None
        facts["head"] = head
        run("04-rev-parse-object-format", ["git", "rev-parse", "--show-object-format=storage"], git_exe)
        raw_format = first_line(outputs["04-rev-parse-object-format"])
        if raw_format is not None and raw_format not in KNOWN_OBJECT_FORMATS:
            # 旧版 Git 不认识该选项时会原样回显并返回 0；不能把回显当成对象格式（原始输出仍保留在 stdout 文件）。
            problems.append("对象格式无法识别或当前 Git 不支持该查询：%r" % raw_format[:80])
            raw_format = None
        facts["object_format"] = raw_format
        if head and raw_format and KNOWN_OBJECT_FORMATS[raw_format] != len(head):
            problems.append("HEAD 长度与对象格式不一致")
        if head:
            run("05-cat-file-type", ["git", "cat-file", "-t", head], git_exe)
            facts["head_object_type"] = first_line(outputs["05-cat-file-type"])
            if facts["head_object_type"] != "commit":
                problems.append("HEAD 对象类型不是 commit")
        else:
            sample["commands"].append({"id": "05-cat-file-type", "argv": ["git", "cat-file", "-t", None],
                                       "executable": git_exe, "returncode": None,
                                       "reason": "skipped_head_unavailable", "duration_seconds": None,
                                       "stdout": None, "stderr": None})
            facts["head_object_type"] = None
            problems.append("05-cat-file-type 未运行：HEAD 不可用")
        status_rec = run("06-status-porcelain", ["git", "-c", "core.fsmonitor=false", "status", "--porcelain=v1",
                                                 "-z", "--untracked-files=all"], git_exe)
        run("07-status-ignored", ["git", "-c", "core.fsmonitor=false", "status", "--porcelain=v1", "-z",
                                  "--ignored=matching", "--untracked-files=all"], git_exe)
        run("08-diff-unstaged", ["git", "--no-pager", "diff", "--no-ext-diff", "--no-textconv", "--binary"], git_exe)
        run("09-diff-staged", ["git", "--no-pager", "diff", "--cached", "--no-ext-diff", "--no-textconv",
                               "--binary"], git_exe)
        config: Dict[str, Any] = {}
        for index, key in enumerate(CONFIG_KEYS):
            rec = run("%02d-config-%s" % (10 + index, key), ["git", "config", "--get", key], git_exe,
                      required=False, ok_codes=(0, 1))
            if rec["returncode"] == 0:
                config[key] = {"status": "set", "value": first_line(outputs[rec["id"]]) or ""}
            elif rec["returncode"] == 1:
                config[key] = {"status": "unset", "value": None}
            else:
                config[key] = {"status": "error", "value": None}
                problems.append("%s 失败：returncode=%s reason=%s" % (rec["id"], rec["returncode"], rec["reason"]))
        facts["git_config"] = config
        run("18-ls-files", ["git", "ls-files", "-z", "--cached"], git_exe)
        bash_rec = run("19-bash-version", ["bash", "--version"], bash_exe, required=False)
        facts["bash_version_first_line"] = first_line(outputs["19-bash-version"])
        facts["bash_status"] = "ok" if bash_rec["returncode"] == 0 else (bash_rec["reason"] or "nonzero_exit")

        status_entries: Optional[List[Dict[str, Any]]] = None
        ignored_entries: Optional[List[Dict[str, Any]]] = None
        tracked_raw: Optional[List[bytes]] = None
        try:
            if outputs.get("06-status-porcelain") is not None:
                status_entries = parse_porcelain_v1_z(outputs["06-status-porcelain"] or b"")
            if outputs.get("07-status-ignored") is not None:
                ignored_entries = parse_porcelain_v1_z(outputs["07-status-ignored"] or b"")
            if outputs.get("18-ls-files") is not None:
                tracked_raw = parse_nul_list(outputs["18-ls-files"] or b"")
        except ValueError as exc:
            problems.append("解析 Git 输出失败：%s" % exc)
        if status_entries is not None:
            facts["porcelain_entries"] = len(status_entries)
            facts["porcelain_sha256"] = status_rec["stdout"]["sha256"]
        if status_entries is not None and ignored_entries is not None and tracked_raw is not None:
            manifest, exclusion_counts = build_input_manifest(ctx.repo_root, status_entries, ignored_entries,
                                                              tracked_raw, excludes)
            sample["exclusion_counts"] = exclusion_counts
            ref = ctx.write_exclusive(phase_dir / "input-manifest.json", canonical_json_bytes(manifest))
            ref["closure_sha256"] = closure_sha256(manifest)
            ref["item_count"] = len(manifest["items"])
            ref["ignored_count"] = manifest["ignored"]["count"]
            sample["input_manifest"] = ref
            sample["_manifest_obj"] = manifest
            if any(not i.get("path_utf8", True) for i in manifest["items"]):
                problems.append("存在不能按 UTF-8 解码的路径，未计算其摘要")
            unreadable = [i["path"] for i in manifest["items"] if str(i.get("note", "")).startswith("read_error")]
            if unreadable:
                problems.append("有 %d 个输入文件无法读取，未计算摘要：%s" % (len(unreadable), ", ".join(unreadable[:10])))
        else:
            problems.append("输入清单未生成：缺少 status/ignored/ls-files 输出")
        env_facts = environment_facts()
        sample["environment"] = ctx.write_exclusive(phase_dir / "environment.json", canonical_json_bytes(env_facts))
    except Exception as exc:  # noqa: BLE001 - 记录为不完整，不吞掉已有记录
        problems.append("采样异常：%s" % exc_text(exc))
    sample["finished_at"] = utc_now()
    sample["complete"] = not problems
    return sample


def new_run_record(argv: Sequence[str], timeout: float, grace: float) -> Dict[str, Any]:
    return {
        "attempted": False, "executed": False,
        "executed_semantics": "attempted：已把命令交给监督器；executed：进程已创建并在监督下恢复运行。"
                              "输出文件写不出来、启动失败时 executed=false；监督器异常时为 null（未知）",
        "argv": list(argv), "argv0_which": shutil.which(argv[0]) if argv and argv[0] else None,
        "cwd": "repo_root", "stdin": "devnull", "shell": False, "timeout_seconds": timeout, "grace_seconds": grace,
        "env_policy": "pi_dispatch.child_env({})：继承当前环境，移除仓库重定向变量与推送/发布类凭据，"
                      "设置 GIT_TERMINAL_PROMPT/GCM_INTERACTIVE，缺省时设置 PYTHONDONTWRITEBYTECODE=1",
        "env_removed_names": None, "env_added_names": None,
        "supervisor": "pi_dispatch.run_supervised", "started_at": None, "finished_at": None,
        "duration_seconds": None, "supervisor_wall_seconds": None, "returncode": None, "reason": None,
        "timed_out": False, "interrupted": False, "spawn_error": None, "termination_confirmed": None,
        "exit_status_after_termination": None, "stray_processes": None, "kill_method": None,
        "stdout": None, "stderr": None, "interpretation": "not_evaluated",
    }


#: 被测命令记录中表示“取证不完整”的 reason，及其在 incomplete_reasons 中的写法。
RUN_REASON_INCOMPLETE = {
    "output_write_failed": "run_output_write_failed",
    "spawn_failed": "run_spawn_failed",
    "supervisor_error": "run_supervisor_error",
    "interrupted": "run_interrupted",
    "exit_status_unavailable": "run_exit_status_unavailable",
}


def run_incomplete_reasons(run: Dict[str, Any]) -> List[str]:
    """由被测命令记录推出取证不完整的原因；命令没有真正运行时一定非空（01 文档 6.3）。"""
    reasons: List[str] = []
    mapped = RUN_REASON_INCOMPLETE.get(run.get("reason") or "")
    if mapped:
        reasons.append(mapped)
    if run.get("reason") == "timeout" and not run.get("termination_confirmed"):
        reasons.append("run_termination_unconfirmed")
    if run.get("output_close_error"):
        reasons.append("run_output_close_failed")
    if run.get("output_record_errors"):
        reasons.append("run_output_unrecorded")
    elif run.get("attempted") and (not run.get("stdout") or not run.get("stderr")):
        reasons.append("run_output_missing")
    if run.get("executed") is not True and not reasons:
        reasons.append("run_not_executed")
    return reasons


def run_command(ctx: CaptureContext, record: Dict[str, Any], supervisor: types.ModuleType) -> None:
    """在现有监督器 pi_dispatch.run_supervised 中运行被测命令，就地填写 record（由 new_run_record 创建）。

    就地填写：即使中途出现异常，调用方手里的记录也保留已经发生的事实。
    """
    argv = list(record["argv"])
    run_dir = ctx.capture_dir / "run"
    out_path, err_path = run_dir / "stdout.bin", run_dir / "stderr.bin"
    env, removed = supervisor.child_env({})
    record["env_removed_names"] = removed
    record["env_added_names"] = sorted(name for name in env if name not in os.environ)
    result: Optional[Dict[str, Any]] = None
    try:
        with contextlib.ExitStack() as stack:
            try:
                run_dir.mkdir()
                out = stack.enter_context(open(out_path, "xb"))
                err = stack.enter_context(open(err_path, "xb"))
            except OSError as exc:
                # 输出文件写不出来：不启动被测命令（证据无处保存），记为取证不完整。
                record.update({"reason": "output_write_failed", "error": exc_text(exc)})
            else:
                record["attempted"] = True
                record["started_at"] = utc_now()
                started = time.monotonic()
                try:
                    result = supervisor.run_supervised(argv, ctx.repo_root, env, out, err,
                                                       record["timeout_seconds"], grace=record["grace_seconds"])
                except Exception as exc:  # noqa: BLE001 - 监督器异常：命令是否运行过未知
                    record.update({"executed": None, "reason": "supervisor_error", "error": exc_text(exc)})
                except BaseException:
                    record.update({"executed": None, "reason": "capture_interrupted"})
                    raise
                finally:
                    record["duration_seconds"] = round(time.monotonic() - started, 6)
                    record["finished_at"] = utc_now()
    except OSError as exc:  # 关闭输出文件失败（写盘错误可能在关闭时才暴露）
        record["output_close_error"] = exc_text(exc)
    finally:
        for key, path in (("stdout", out_path), ("stderr", err_path)):
            try:
                if path.is_file():
                    record[key] = ctx.file_ref(path)
            except OSError as exc:
                record.setdefault("output_record_errors", []).append("%s: %s" % (key, exc_text(exc)))
    if result is None:
        return
    record["executed"] = not result.get("spawn_error") and result.get("pid") is not None
    record["supervisor_wall_seconds"] = result.get("wall_seconds")
    record["timed_out"] = bool(result.get("timed_out"))
    record["interrupted"] = bool(result.get("interrupted"))
    record["stray_processes"] = result.get("stray_processes")
    record["kill_method"] = result.get("kill_method")
    code = result.get("exit_code")
    if result.get("spawn_error"):
        record["spawn_error"] = safe_text(str(result["spawn_error"]))
        record.update({"returncode": None, "reason": "spawn_failed"})
    elif record["interrupted"]:
        record.update({"returncode": None, "reason": "interrupted", "exit_status_after_termination": code,
                       "termination_confirmed": code is not None})
    elif record["timed_out"]:
        record.update({"returncode": None, "reason": "timeout", "exit_status_after_termination": code,
                       "termination_confirmed": code is not None})
    else:
        record.update(interpret_returncode(code))


def compare_samples(pre: Dict[str, Any], post: Dict[str, Any]) -> Dict[str, Any]:
    drift: List[Dict[str, Any]] = []
    observations: List[Dict[str, Any]] = []
    comparison: Dict[str, Any] = {"baseline_consistent": None, "drift": drift, "observations": observations,
                                  "checked": [], "unavailable": []}

    def cmd(sample: Dict[str, Any], cmd_id: str) -> Optional[Dict[str, Any]]:
        for record in sample["commands"]:
            if record["id"] == cmd_id:
                return record
        return None

    def check(name: str, a: Any, b: Any, extra: Optional[Dict[str, Any]] = None) -> None:
        if a is None or b is None:
            comparison["unavailable"].append(name)
            return
        comparison["checked"].append(name)
        if a != b:
            entry = {"check": name, "pre": a, "post": b}
            if extra:
                entry.update(extra)
            drift.append(entry)

    def out_sha(sample: Dict[str, Any], cmd_id: str) -> Optional[str]:
        record = cmd(sample, cmd_id)
        if not record or record["returncode"] != 0 or not record["stdout"]:
            return None
        return record["stdout"]["sha256"]

    pf, qf = pre["facts"], post["facts"]
    check("head", pf.get("head"), qf.get("head"))
    check("object_format", pf.get("object_format"), qf.get("object_format"))
    # porcelain 原始字节；不同时列出状态有差异的路径
    a, b = out_sha(pre, "06-status-porcelain"), out_sha(post, "06-status-porcelain")
    paths: List[str] = []
    if a is not None and b is not None and a != b:
        pre_map = {e["path"]: (e["xy"], e["orig_path"]) for e in pre.get("_status_entries", [])}
        post_map = {e["path"]: (e["xy"], e["orig_path"]) for e in post.get("_status_entries", [])}
        paths = sorted(p for p in set(pre_map) | set(post_map) if pre_map.get(p) != post_map.get(p))
    check("porcelain_raw_bytes", a, b, {"paths": paths})
    # 输入清单：整份 input-manifest.json 的 sha256 决定漂移（含忽略项名称）；逐文件、逐项列出差异，
    # 保证每条漂移都能解释。闭包摘要（去掉忽略项）是否相同另行记录，供报告区分。
    ma, mb = pre.get("_manifest_obj"), post.get("_manifest_obj")
    if ma is not None and mb is not None:
        changes: List[Dict[str, Any]] = []
        items_a = {i["path"]: i for i in ma["items"]}
        items_b = {i["path"]: i for i in mb["items"]}
        for path in sorted(set(items_a) | set(items_b)):
            ia, ib = items_a.get(path), items_b.get(path)
            if ia is None:
                changes.append({"path": path, "change": "added", "post": ib})
            elif ib is None:
                changes.append({"path": path, "change": "removed", "pre": ia})
            elif ia != ib:
                fields = sorted(k for k in set(ia) | set(ib) if ia.get(k) != ib.get(k))
                changes.append({"path": path, "change": "modified", "fields": fields,
                                "pre": {k: ia.get(k) for k in fields}, "post": {k: ib.get(k) for k in fields}})
        ign_a, ign_b = set(ma["ignored"]["names"]), set(mb["ignored"]["names"])
        ign_added, ign_removed = sorted(ign_b - ign_a), sorted(ign_a - ign_b)
        other_fields: List[Dict[str, Any]] = []
        for key in sorted(set(ma) | set(mb)):
            if key in ("items", "ignored") or ma.get(key) == mb.get(key):
                continue
            other_fields.append({"field": key, "pre": ma.get(key), "post": mb.get(key)})
        ig_a, ig_b = ma.get("ignored") or {}, mb.get("ignored") or {}
        for key in sorted(set(ig_a) | set(ig_b)):
            if key in ("names", "count") or ig_a.get(key) == ig_b.get(key):
                continue
            other_fields.append({"field": "ignored." + key, "pre": ig_a.get(key), "post": ig_b.get(key)})
        closure_equal = pre["input_manifest"]["closure_sha256"] == post["input_manifest"]["closure_sha256"]
        check("input_manifest_sha256", pre["input_manifest"]["sha256"], post["input_manifest"]["sha256"],
              {"paths": [c["path"] for c in changes], "changes": changes,
               "ignored_names_added": ign_added[:500], "ignored_names_removed": ign_removed[:500],
               "ignored_names_truncated": len(ign_added) > 500 or len(ign_removed) > 500,
               "other_fields": other_fields,
               "explained": bool(changes or ign_added or ign_removed or other_fields),
               "closure_sha256_equal": closure_equal,
               "note": "closure_sha256_equal=true 表示变化只在忽略项名称上（忽略文件未纳入输入闭包）"})
        comparison["input_manifest_closure_sha256_equal"] = closure_equal
    else:
        comparison["unavailable"].append("input_manifest_sha256")
    xa, xb = pre.get("exclusion_counts"), post.get("exclusion_counts")
    if xa is not None and xb is not None and xa != xb:
        observations.append({"observation": "excluded_path_counts_changed", "not_counted_as_drift": True,
                             "pre": xa, "post": xb,
                             "note": "被 --exclude 排除的路径不在输入清单中；其状态变化仍可能体现在 porcelain 原始字节中"})
    check("diff_unstaged_bytes", out_sha(pre, "08-diff-unstaged"), out_sha(post, "08-diff-unstaged"))
    check("diff_staged_bytes", out_sha(pre, "09-diff-staged"), out_sha(post, "09-diff-staged"))
    check("ls_files_bytes", out_sha(pre, "18-ls-files"), out_sha(post, "18-ls-files"))
    check("head_object_type", pf.get("head_object_type"), qf.get("head_object_type"))
    check("git_version", pf.get("git_version"), qf.get("git_version"))
    check("git_config", pf.get("git_config"), qf.get("git_config"))
    check("bash_version_first_line", pf.get("bash_version_first_line") or pf.get("bash_status"),
          qf.get("bash_version_first_line") or qf.get("bash_status"))
    ea, eb = pre.get("environment"), post.get("environment")
    check("environment_facts_sha256", ea and ea["sha256"], eb and eb["sha256"])
    if pre["complete"] and post["complete"] and not comparison["unavailable"]:
        comparison["baseline_consistent"] = not drift
    else:
        comparison["reason_unknown"] = "前或后采样不完整，无法判定基线一致性"
    return comparison


def public_sample(sample: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if sample is None:
        return None
    return {k: v for k, v in sample.items() if not k.startswith("_")}


# ---------------------------------------------------------------------------
# capture
# ---------------------------------------------------------------------------

def cmd_capture(opts: argparse.Namespace, argv_cmd: List[str]) -> int:
    try:
        supervisor, supervisor_info = load_supervisor()
    except Exception as exc:  # noqa: BLE001
        print("ERROR: 无法加载监督器 scripts/pi_dispatch.py：%s" % exc_text(exc), file=sys.stderr)
        return EXIT_INCOMPLETE
    git_env = supervisor.git_env()
    repo_root, error = git_toplevel(git_env)
    if repo_root is None:
        print("ERROR: 无法确定仓库根（git rev-parse --show-toplevel）：%s" % error, file=sys.stderr)
        return EXIT_INCOMPLETE
    out_root = Path(opts.out_root)
    if not out_root.is_absolute():
        out_root = repo_root / out_root
    capture_id = opts.capture_id or default_capture_id()
    capture_dir = out_root / capture_id
    excludes = list(dict.fromkeys(opts.exclude)) if opts.exclude else list(DEFAULT_EXCLUDES)

    created_parents: List[Path] = []
    probe = out_root
    while not probe.exists() and probe.parent != probe:
        created_parents.append(probe)
        probe = probe.parent
    try:
        out_root.mkdir(parents=True, exist_ok=True)
        os.mkdir(str(capture_dir))
    except FileExistsError:
        print("ERROR: 取证目录已存在，拒绝覆盖：%s" % capture_dir, file=sys.stderr)
        return EXIT_INCOMPLETE
    except OSError as exc:
        print("ERROR: 无法创建取证目录：%s" % exc_text(exc), file=sys.stderr)
        return EXIT_INCOMPLETE

    repo_rel = relative_within(str(capture_dir), str(repo_root))
    location: Dict[str, Any] = {"inside_repo": repo_rel is not None, "repo_relative": None,
                                "git_ignored": None, "covered_by_exclude": None}
    if repo_rel is not None:
        rel = repo_rel
        location["repo_relative"] = rel
        location["covered_by_exclude"] = match_exclusion(rel + "/", excludes)
        try:
            proc = subprocess.run(["git", "check-ignore", "-q", "--", rel], cwd=str(repo_root), env=git_env,
                                  stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                  timeout=SAMPLE_COMMAND_TIMEOUT)
            location["git_ignored"] = proc.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            location["git_ignored"] = False
        if not location["git_ignored"]:
            # 只删除本次刚创建、仍为空的目录（os.rmdir 不会删除非空目录）。
            for path in [capture_dir] + created_parents:
                try:
                    os.rmdir(str(path))
                except OSError:
                    break
            print("ERROR: 取证目录位于仓库内但未被 Git 忽略，取证文件会进入被采样的输入范围：%s。"
                  "请改用仓库外目录或已忽略的目录（例如 .agent/baseline/）。" % rel, file=sys.stderr)
            return EXIT_USAGE

    ctx = CaptureContext(capture_dir, repo_root)
    record: Dict[str, Any] = {
        "schema_version": CAPTURE_SCHEMA_VERSION,
        "record_type": "baseline-capture",
        "capture_id": capture_id,
        "started_at": utc_now(),
        "finished_at": None,
        "tool": None,
        "supervisor": supervisor_info,
        "command": {"argv": list(argv_cmd), "timeout_seconds": opts.timeout, "grace_seconds": opts.grace},
        "output_location": location,
        "excludes": excludes,
        "git_sampling_env_policy": "pi_dispatch.git_env()：移除 Git 重定向变量，GIT_OPTIONAL_LOCKS=0，"
                                   "GIT_TERMINAL_PROMPT=0，GCM_INTERACTIVE=never",
        "pre": None, "run": None, "post": None, "comparison": None,
        "execution_status": "incomplete",
        "execution_status_scope": "只描述取证本身是否完整，不解释被测命令是否通过（01 文档 2.4、6.3）",
        "incomplete_reasons": [],
        "limitations": list(STATIC_LIMITATIONS),
        "files": ctx.files,
    }
    reasons: List[str] = record["incomplete_reasons"]
    if location["inside_repo"] and not location["covered_by_exclude"]:
        record["limitations"].append("取证目录位于仓库内且未被 --exclude 覆盖：若忽略规则按文件而不是按目录匹配，"
                                     "取证文件会进入忽略项名单并产生漂移；建议把该目录加入 --exclude。")
    pre = post = None
    try:
        record["tool"] = tool_self_info(repo_root)
        present_redirects = [name for name in GIT_REDIRECT_NAMES if name in os.environ]
        if present_redirects:
            record["limitations"].append("环境中设置了 %s：采样命令已移除这些变量，被测命令也经 child_env 移除；"
                                         "若被测流程依赖它们，结果不代表原环境。" % ", ".join(present_redirects))
        git_exe, bash_exe = shutil.which("git"), shutil.which("bash")
        pre = take_sample(ctx, "pre", git_env, excludes, git_exe, bash_exe)
        pre["_status_entries"] = _status_entries_of(ctx, pre)
        record["pre"] = pre
        run = new_run_record(argv_cmd, opts.timeout, opts.grace)
        record["run"] = run
        if not pre["complete"]:
            reasons.append("pre_sample_incomplete")
            run["reason"] = "not_run_pre_sample_incomplete"
        else:
            run_command(ctx, run, supervisor)
            reasons.extend(run_incomplete_reasons(run))
            if run["stray_processes"]:
                record["limitations"].append("被测命令主进程结束后仍有残留子进程，已由监督器结束。")
            if run["reason"] != "interrupted":
                post = take_sample(ctx, "post", git_env, excludes, git_exe, bash_exe)
                post["_status_entries"] = _status_entries_of(ctx, post)
                record["post"] = post
                if not post["complete"]:
                    reasons.append("post_sample_incomplete")
                record["comparison"] = compare_samples(pre, post)
                record["comparison"]["command_executed"] = run["executed"]
                if run["executed"] is not True:
                    record["comparison"]["command_note"] = "被测命令没有真正运行；前后比较只说明取证期间的工作区变化"
    except KeyboardInterrupt:
        reasons.append("capture_interrupted")
    except Exception as exc:  # noqa: BLE001
        reasons.append("capture_error: %s" % exc_text(exc))
    if record["comparison"] is None:
        record["comparison"] = {"baseline_consistent": None, "drift": [], "observations": [],
                                "reason_unknown": "没有完成前后采样比较"}
    record["pre"], record["post"] = public_sample(pre), public_sample(post)
    record["finished_at"] = utc_now()
    record["execution_status"] = "complete" if not reasons else "incomplete"
    try:
        with open(capture_dir / "capture.json", "xb") as handle:
            handle.write(canonical_json_bytes(record))
    except Exception as exc:  # noqa: BLE001
        print("ERROR: 无法写出 capture.json：%s" % exc_text(exc), file=sys.stderr)
        return EXIT_INCOMPLETE
    print_capture_summary(capture_dir, record)
    return EXIT_OK if record["execution_status"] == "complete" else EXIT_INCOMPLETE


def _status_entries_of(ctx: CaptureContext, sample: Dict[str, Any]) -> List[Dict[str, Any]]:
    for rec in sample["commands"]:
        if rec["id"] == "06-status-porcelain" and rec["returncode"] == 0 and rec["stdout"]:
            try:
                return parse_porcelain_v1_z(read_ref(ctx, rec["stdout"]) or b"")
            except (OSError, ValueError):
                return []
    return []


def print_capture_summary(capture_dir: Path, record: Dict[str, Any]) -> None:
    run = record.get("run") or {}
    comparison = record.get("comparison") or {}
    lines = [
        "capture_dir: %s" % capture_dir,
        "execution_status: %s%s" % (record["execution_status"],
                                    (" (%s)" % ", ".join(record["incomplete_reasons"]))
                                    if record["incomplete_reasons"] else ""),
        "run: executed=%s returncode=%s reason=%s timed_out=%s duration=%ss" % (
            run.get("executed"), run.get("returncode"), run.get("reason"), run.get("timed_out"),
            run.get("duration_seconds")),
        "baseline_consistent: %s" % comparison.get("baseline_consistent"),
        "drift: %s" % (", ".join(d["check"] for d in comparison.get("drift", [])) or "none"),
        "note: exit code reports capture completeness only; whether the command passed is judged in the report",
    ]
    for line in lines:
        print(line)


# ---------------------------------------------------------------------------
# archive（版本化脱敏）
# ---------------------------------------------------------------------------

#: 路径分隔符：一个或多个反斜杠/正斜杠，覆盖 JSON/Python 转义（含多层转义）与混用写法。
_SEP_RE = r"[\\/]+"


def windows_path_aliases(path: str) -> List[str]:
    """Windows：返回同一路径的 8.3 短名形式与长名形式（GetShortPathNameW / GetLongPathNameW）。

    只在调用时加载 kernel32；路径不存在、卷未生成短名或不是 Windows 时返回空列表或与原值相同的形式。
    """
    if os.name != "nt":
        return []
    try:
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # 独立实例，不改动全局 windll 的函数原型
    except (ImportError, OSError, AttributeError):
        return []
    aliases: List[str] = []
    for name in ("GetShortPathNameW", "GetLongPathNameW"):
        func = getattr(kernel32, name, None)
        if func is None:
            continue
        func.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
        func.restype = wintypes.DWORD
        size = 512
        for _attempt in range(4):
            buf = ctypes.create_unicode_buffer(size)
            needed = func(path, buf, size)
            if needed == 0:
                break
            if needed < size:
                aliases.append(buf.value)
                break
            size = needed + 1
    return aliases


def _split_root(path: str) -> Optional[Tuple[str, List[str]]]:
    """把绝对路径拆成 (根的种类, 分段列表)；相对路径、文件系统根或过短的路径返回 None（替换会误伤）。"""
    trimmed = path.rstrip("\\/")
    if trimmed.startswith(("\\\\?\\", "\\\\.\\", "//?/", "//./")):
        trimmed = trimmed[4:]
        if trimmed[:4].upper() in ("UNC\\", "UNC/"):
            trimmed = "\\\\" + trimmed[4:]
    if len(trimmed) < 4:
        return None
    drive = re.match(r"^([A-Za-z]):[\\/]+(.+)$", trimmed)
    if drive:
        kind, rest = "drive:" + drive.group(1).lower(), drive.group(2)
    elif re.match(r"^[\\/]{2}[^\\/]", trimmed):
        kind, rest = "unc", trimmed[2:]
    elif trimmed[:1] in ("/", "\\"):
        kind, rest = "rooted", trimmed[1:]
    else:
        return None
    parts = [part for part in re.split(r"[\\/]+", rest) if part]
    return (kind, parts) if parts else None


def root_patterns(value: str) -> List[Tuple[str, int, int]]:
    """为一个根路径生成按分段匹配的正则 [(regex, 分段数, 最长写法长度)]。

    写法来源：原值、realpath，以及二者在 Windows 上的 8.3 短名与长名形式。分段数相同的写法逐段合并为
    “长名|短名”的备选，所以只有部分分段写成短名的混合写法（例如 C:\\Users\\ADMINI~1\\AppData\\...\\长名目录）
    也能匹配。盘符可写成 C: 或 MSYS 的 /c。
    """
    variants: List[str] = []
    bases = [value]
    try:
        bases.append(os.path.realpath(value))
    except (OSError, ValueError):
        pass
    for base in bases:
        variants.append(base)
        variants.extend(windows_path_aliases(base))
    groups: Dict[Tuple[str, int], List[Dict[str, str]]] = {}
    order: List[Tuple[str, int]] = []
    for variant in variants:
        split = _split_root(variant)
        if split is None:
            continue
        kind, parts = split
        key = (kind, len(parts))
        if key not in groups:
            groups[key] = [{} for _ in parts]
            order.append(key)
        for slot, part in zip(groups[key], parts):
            slot.setdefault(part.lower(), part)
    patterns: List[Tuple[str, int, int]] = []
    for kind, count in order:
        slots = groups[(kind, count)]
        if kind.startswith("drive:"):
            letter = re.escape(kind[len("drive:"):])
            head = "(?:%s:|/%s)%s" % (letter, letter, _SEP_RE)
        elif kind == "unc":
            head = _SEP_RE * 2
        else:
            head = _SEP_RE
        body = _SEP_RE.join(
            "(?:%s)" % "|".join(re.escape(name) for name in sorted(slot.values(), key=lambda s: (-len(s), s)))
            for slot in slots)
        longest = sum(max(len(name) for name in slot.values()) for slot in slots)
        patterns.append((head + body, count, longest))
    return patterns


def text_encoding(data: bytes) -> Optional[str]:
    """归档时按什么编码解释文本：疑似无 BOM 的 UTF-16 返回 utf-16-le/be，否则 utf-8，都不像则返回 None。

    以 ASCII 为主的 UTF-16 文本也能按 UTF-8 解码（NUL 是合法字节），直接当 UTF-8 处理会让路径匹配失效，
    却被标成“已脱敏”。所以先看 NUL 是否集中在一种奇偶位置。
    """
    if len(data) >= 4 and len(data) % 2 == 0:
        half = len(data) // 2
        even_nuls, odd_nuls = data[0::2].count(0), data[1::2].count(0)
        for encoding, nuls, others in (("utf-16-le", odd_nuls, even_nuls), ("utf-16-be", even_nuls, odd_nuls)):
            if nuls * 2 >= half and others * 4 < half:
                try:
                    data.decode(encoding)
                except UnicodeDecodeError:
                    return None
                return encoding
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return "utf-8"


class Redactor:
    """redact-v2：把机器定位替换为占位符。

    按路径分段匹配，大小写不敏感：每段可为长名或 Windows 8.3 短名（含混合写法）；分隔符为一个或多个反斜杠/
    正斜杠（覆盖 JSON 转义与多层转义）；盘符写法为 C: 或 MSYS /c。分段更多（更具体）的根优先，分段数相同时按
    REDACTION_CATEGORIES 的顺序；匹配后不能紧跟 [A-Za-z0-9_~-]（避免把 C:/Users/ab 当作 C:/Users/abc 的前缀）。
    """

    def __init__(self, roots: Dict[str, List[str]]) -> None:
        entries: List[Tuple[str, str, int, int]] = []
        seen = set()
        for category in REDACTION_CATEGORIES:
            for value in roots.get(category, []):
                if not value:
                    continue
                for regex, count, longest in root_patterns(value):
                    key = regex.lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    entries.append((regex, category, count, longest))
        entries.sort(key=lambda entry: (-entry[2], -entry[3]))  # 稳定排序：并列时保持类别优先级
        self.categories = [entry[1] for entry in entries]
        self.pattern_counts = {c: sum(1 for entry in entries if entry[1] == c) for c in REDACTION_CATEGORIES}
        alternation = "|".join("(?P<g%d>%s)" % (index, entry[0]) for index, entry in enumerate(entries))
        self.pattern = re.compile("(?:%s)(?![A-Za-z0-9_~-])" % alternation, re.IGNORECASE) if entries else None

    def redact(self, text: str) -> Tuple[str, Dict[str, int]]:
        counts = {c: 0 for c in REDACTION_CATEGORIES}
        if self.pattern is None:
            return text, counts

        def repl(match: "re.Match[str]") -> str:
            category = self.categories[int((match.lastgroup or "g0")[1:])]
            counts[category] += 1
            return category

        return self.pattern.sub(repl, text), counts


def cmd_archive(opts: argparse.Namespace) -> int:
    capture_dir = Path(opts.capture_dir).resolve()
    capture_json = capture_dir / "capture.json"
    if not capture_dir.is_dir() or not capture_json.is_file():
        print("ERROR: 不是取证目录（缺少 capture.json）：%s" % capture_dir, file=sys.stderr)
        return EXIT_INCOMPLETE
    try:
        record = json.loads(capture_json.read_bytes().decode("utf-8"))
    except (OSError, ValueError) as exc:
        print("ERROR: 无法读取 capture.json：%s" % exc_text(exc), file=sys.stderr)
        return EXIT_INCOMPLETE
    capture_id = record.get("capture_id") if isinstance(record, dict) else None
    if not isinstance(capture_id, str) or capture_id != capture_dir.name or validate_capture_id(capture_id):
        print("ERROR: capture.json 的 capture_id 与目录名不一致或不合法", file=sys.stderr)
        return EXIT_INCOMPLETE
    # 先核对取证记录中的每个文件摘要：摘要不符时不发布归档（01 文档 8.3）。
    listed: Dict[str, str] = {}
    mismatches: List[str] = []
    refs = record.get("files")
    if not isinstance(refs, list) or not all(isinstance(r, dict) and isinstance(r.get("path"), str) for r in refs):
        print("ERROR: capture.json 缺少合法的 files 列表", file=sys.stderr)
        return EXIT_INCOMPLETE
    for ref in refs:
        path = capture_dir / ref["path"]
        if not is_within(str(path), str(capture_dir)):
            mismatches.append(ref["path"])
            continue
        try:
            digest, size = sha256_file(path)
        except OSError:
            mismatches.append(ref["path"])
            continue
        if digest != ref.get("sha256") or size != ref.get("bytes"):
            mismatches.append(ref["path"])
        listed[ref["path"]] = digest
    if mismatches:
        print("ERROR: 取证文件与 capture.json 记录的摘要不符，拒绝归档：%s" % ", ".join(mismatches[:20]),
              file=sys.stderr)
        return EXIT_INCOMPLETE
    files: List[str] = []
    for dirpath, dirnames, filenames in os.walk(str(capture_dir), followlinks=False):
        dirnames.sort()
        for name in list(dirnames):
            if os.path.islink(os.path.join(dirpath, name)):
                print("ERROR: 取证目录中有符号链接，拒绝归档：%s" % name, file=sys.stderr)
                return EXIT_INCOMPLETE
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            if not stat.S_ISREG(os.lstat(full).st_mode):
                print("ERROR: 取证目录中有非普通文件，拒绝归档：%s" % name, file=sys.stderr)
                return EXIT_INCOMPLETE
            files.append(os.path.relpath(full, str(capture_dir)).replace("\\", "/"))

    repo_root, _ = git_toplevel(_plain_git_env())
    dest = Path(opts.dest)
    if not dest.is_absolute():
        if repo_root is None:
            print("ERROR: --dest 是相对路径，但当前目录不在 Git 仓库中，无法按仓库根解析", file=sys.stderr)
            return EXIT_USAGE
        dest = repo_root / dest
    target = dest / capture_id
    if is_within(str(target), str(capture_dir)):
        print("ERROR: 归档目标不能位于取证目录内", file=sys.stderr)
        return EXIT_USAGE

    roots: Dict[str, List[str]] = {c: [] for c in REDACTION_CATEGORIES}
    captured_top = _captured_toplevel(capture_dir, record)
    if captured_top:
        roots["<REPO>"].append(captured_top)
    if repo_root is not None:
        roots["<REPO>"].append(str(repo_root))
    roots["<HOME>"].extend([str(Path.home()), os.path.expanduser("~")])
    roots["<TEMP>"].append(tempfile.gettempdir())
    roots["<PYDIR>"].append(os.path.dirname(sys.executable))
    captured_python = _captured_python_executable(capture_dir, record)
    if captured_python:
        roots["<PYDIR>"].append(os.path.dirname(captured_python))
    redactor = Redactor(roots)

    try:
        dest.mkdir(parents=True, exist_ok=True)
        os.mkdir(str(target))
    except FileExistsError:
        print("ERROR: 归档目录已存在，拒绝覆盖：%s" % target, file=sys.stderr)
        return EXIT_INCOMPLETE
    except OSError as exc:
        print("ERROR: 无法创建归档目录：%s" % exc_text(exc), file=sys.stderr)
        return EXIT_INCOMPLETE

    entries: List[Dict[str, Any]] = []
    try:
        for rel in files:
            data = (capture_dir / rel).read_bytes()
            encoding = text_encoding(data)
            text = data.decode(encoding) if encoding is not None else None
            if text is None:
                out_data, representation, counts, revision = data, "captured_raw_copy", None, None
            else:
                redacted, counts = redactor.redact(text)
                out_data, representation, revision = redacted.encode(encoding), "redacted_raw", REDACTION_RULE_REVISION
            out_path = target / rel
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "xb") as handle:
                handle.write(out_data)
            entry = {"path": rel, "representation": representation, "redaction_rule_revision": revision,
                     "redacted": representation == "redacted_raw",
                     "original_sha256": sha256_bytes(data), "original_bytes": len(data),
                     "archived_sha256": sha256_bytes(out_data), "archived_bytes": len(out_data),
                     "length_changed": len(out_data) != len(data), "bytes_changed": out_data != data,
                     "replacements": counts, "listed_in_capture_json": rel in listed or rel == "capture.json",
                     "text_encoding": encoding}
            if representation == "captured_raw_copy":
                entry["note"] = "不能按 UTF-8 或 UTF-16 解码，原样复制，未脱敏，可能含机器路径"
            entries.append(entry)
        manifest = {
            "schema_version": 1,
            "record_type": "baseline-archive-manifest",
            "unredacted_files": [e["path"] for e in entries if not e["redacted"]],
            "capture_id": capture_id,
            "created_at": utc_now(),
            "tool": tool_self_info(repo_root),
            "source_capture_json_sha256": sha256_bytes(capture_json.read_bytes()),
            "integrity_check": {"files_listed_in_capture_json": len(listed), "mismatches": 0},
            "redaction": {
                "rule_revision": REDACTION_RULE_REVISION,
                "placeholders": list(REDACTION_CATEGORIES),
                "categories": {"<REPO>": "仓库根（取证时的 toplevel 与归档时的仓库根）", "<HOME>": "用户主目录",
                               "<TEMP>": "系统临时目录", "<PYDIR>": "sys.executable 所在目录"},
                "pattern_counts": redactor.pattern_counts,
                "matching": "按路径分段匹配，大小写不敏感；写法来源为原值、realpath 及二者在 Windows 上的 8.3 短名/长名"
                            "（GetShortPathNameW/GetLongPathNameW），逐段可取长名或短名（覆盖混合写法）；"
                            "分隔符为一个或多个反斜杠/正斜杠（覆盖 JSON 转义与多层转义），可混用；盘符写法 C: 或 MSYS /c；"
                            "分段更多的根优先；匹配后不能紧跟 [A-Za-z0-9_~-]",
                "text_criterion": "NUL 集中在一种奇偶偏移（至少一半）且能按 UTF-16-LE/BE 严格解码的文件按 UTF-16 脱敏并按原编码"
                                  "写回；其余能按严格 UTF-8 解码（允许 NUL）的文件按 UTF-8 脱敏；都不行则原样复制并标注未脱敏",
                "values_recorded": False,
                "not_covered": ["\\\\?\\ 设备路径前缀写法、/cygdrive/c 写法、file:// URL 与百分号编码写法",
                                "\\uXXXX 转义或其他编码形式的非 ASCII 路径",
                                "8.3 短名只在归档时路径仍存在、且卷启用短名生成时可得；取证后已删除的目录的短名写法不覆盖",
                                "短名/长名与 realpath 以外的别名（subst 盘符、映射网络盘、硬链接、Unicode 规范化差异）",
                                "其他机器路径（例如 Git/工具安装目录）"],
            },
            "files": entries,
        }
        with open(target / "archive-manifest.json", "xb") as handle:
            handle.write(canonical_json_bytes(manifest))
    except Exception as exc:  # noqa: BLE001 - 不完整的归档保留原样（没有 archive-manifest.json）
        print("ERROR: 归档未完成（已写出的文件保留，缺少 archive-manifest.json）：%s" % exc_text(exc),
              file=sys.stderr)
        return EXIT_INCOMPLETE
    changed = sum(1 for e in entries if e["bytes_changed"])
    raw = sum(1 for e in entries if e["representation"] == "captured_raw_copy")
    print("archive_dir: %s" % target)
    print("files: %d  redacted_changed: %d  raw_copies: %d  rule: %s" % (len(entries), changed, raw,
                                                                         REDACTION_RULE_REVISION))
    return EXIT_OK


def _plain_git_env() -> Dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k.upper() not in GIT_REDIRECT_NAMES}
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_OPTIONAL_LOCKS"] = "0"
    return env


def _find_command(record: Dict[str, Any], cmd_id: str) -> Optional[Dict[str, Any]]:
    pre = record.get("pre") or {}
    for rec in pre.get("commands") or []:
        if isinstance(rec, dict) and rec.get("id") == cmd_id:
            return rec
    return None


def _captured_toplevel(capture_dir: Path, record: Dict[str, Any]) -> Optional[str]:
    rec = _find_command(record, "02-rev-parse-toplevel")
    if not rec or not rec.get("stdout"):
        return None
    try:
        text = (capture_dir / rec["stdout"]["path"]).read_bytes().decode("utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return None
    return text or None


def _captured_python_executable(capture_dir: Path, record: Dict[str, Any]) -> Optional[str]:
    ref = (record.get("pre") or {}).get("environment")
    if not ref:
        return None
    try:
        facts = json.loads((capture_dir / ref["path"]).read_bytes().decode("utf-8"))
        value = facts["python"]["executable"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return value if isinstance(value, str) else None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class _UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # type: ignore[override]
        raise _UsageError(message)


def _positive_float(value: str) -> float:
    try:
        number = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("需要数字：%r" % value)
    if not number > 0 or number != number or number == float("inf"):
        raise argparse.ArgumentTypeError("必须是有限正数：%r" % value)
    return number


def _non_negative_float(value: str) -> float:
    try:
        number = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("需要数字：%r" % value)
    if not number >= 0 or number == float("inf"):
        raise argparse.ArgumentTypeError("必须是有限非负数：%r" % value)
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="baseline.py", description="01-T1 基线取证工具")
    sub = parser.add_subparsers(dest="command")
    cap = sub.add_parser("capture", help="前后采样并在监督器中运行被测命令（命令写在 -- 之后）")
    cap.add_argument("--out-root", required=True, help="取证输出根目录；相对路径按仓库根解析")
    cap.add_argument("--capture-id", default=None, help="默认 bl-YYYYMMDDTHHMMSSZ-<8位hex>")
    cap.add_argument("--timeout", type=_positive_float, default=DEFAULT_TIMEOUT, help="被测命令时限（秒，默认 3600）")
    cap.add_argument("--grace", type=_non_negative_float, default=DEFAULT_GRACE,
                     help="超时后结束进程树前的宽限（秒，默认 15，与 run_supervised 相同）")
    cap.add_argument("--exclude", action="append", default=None,
                     help="从输入清单排除的仓库相对精确前缀（以 / 结尾）或精确路径；可重复；默认 .agent/baseline/")
    arc = sub.add_parser("archive", help="校验并复制取证目录，按 redact-v2 脱敏")
    arc.add_argument("capture_dir")
    arc.add_argument("--dest", required=True, help="归档根目录；相对路径按仓库根解析")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass
    parser = build_parser()
    command_argv: List[str] = []
    if args and args[0] == "capture":
        if "--" not in args:
            print("usage error: capture 需要用 -- 分隔被测命令，例如：capture --out-root DIR -- python -c \"print(1)\"",
                  file=sys.stderr)
            return EXIT_USAGE
        split = args.index("--")
        args, command_argv = args[:split], args[split + 1:]
        if not command_argv or not command_argv[0]:
            print("usage error: -- 之后缺少被测命令", file=sys.stderr)
            return EXIT_USAGE
    try:
        opts = parser.parse_args(args)
    except _UsageError as exc:
        print("usage error: %s" % exc, file=sys.stderr)
        return EXIT_USAGE
    except SystemExit as exc:  # --help
        return int(exc.code or 0)
    if opts.command == "capture":
        if opts.capture_id is not None:
            problem = validate_capture_id(opts.capture_id)
            if problem:
                print("usage error: %s" % problem, file=sys.stderr)
                return EXIT_USAGE
        for entry in opts.exclude or []:
            problem = validate_exclude(entry)
            if problem:
                print("usage error: --exclude %r：%s" % (entry, problem), file=sys.stderr)
                return EXIT_USAGE
        return cmd_capture(opts, command_argv)
    if opts.command == "archive":
        return cmd_archive(opts)
    parser.print_usage(sys.stderr)
    return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
