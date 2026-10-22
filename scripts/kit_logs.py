#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kit_logs —— 只读的运行证据与用量查看器：列出、查看、搜索 `.agent/runs`，汇总执行端与规划端用量。

用法：
  python scripts/kit_logs.py list [--task ID] [--state S] [--json]          运行证据的 attempt 清单
  python scripts/kit_logs.py show TARGET [--json]                          一个 attempt 的状态、摘要与证据清单
  python scripts/kit_logs.py search PATTERN [--task ID] [--max N] [--json] 在证据的文本文件里搜索（脱敏之后的文本）
  python scripts/kit_logs.py cat TARGET PATH [--cursor C] [--limit N] [--json]
                                                                            按页读一个证据文件（脱敏之后的文本）
  python scripts/kit_logs.py usage [--task ID] [--transcript PATH]… [--since T] [--until T] [--json]
                                                                            执行端与规划端的 token 用量（下界）

TARGET 的四种写法：`task.vN`（按 meta.json 的 plan_version 选）、`task`（编号最大的 attempt）、
`task/attempt-NNN`、以及显式路径（相对于当前工作目录；`..` 按段栈逐段处理，出栈越过 runs 根或经过链接即拒绝）。
四种写法解析出来的目标都还要真的位于 runs 之下：resolve 之后用 is_within 兜底核对，这一步独立于链接检查。

列举失败按层处理（B11(a)）：runs 根列不出来是退出码 1；目标解析中列不出来、目标 attempt 的证据目录列不出来是
退出码 2；其余目录跳过且不计数。正则、时间换算与深嵌套 JSON 的溢出/递归都按合同归类，不冒出堆栈（B11(c)）。

只读：不写、不改、不删 `.agent/` 下的任何文件；不自动查找会话记录，规划端只统计 `--transcript` 显式给出的路径，
也不输出会话记录的正文。链接（符号链接、junction 与其它重解析点）一律不跟随、计入“跳过的链接”。
只依赖标准库，Python 3.10 可运行。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import pi_dispatch as pd  # noqa: E402

# 正则的语法分析是私有模块（logs search 用，第 58 轮）：环境里的 Python 固定为 3.12.10（.agent/environment.md），
# 升级时核对；3.10 叫 sre_parse、sre_constants（本文件头写明 3.10 可运行）。
try:
    import re._constants as _re_constants  # noqa: E402
    import re._parser as _re_parser  # noqa: E402
except ImportError:  # pragma: no cover - Python 3.10
    import sre_constants as _re_constants  # type: ignore[no-redef]  # noqa: E402
    import sre_parse as _re_parser  # type: ignore[no-redef]  # noqa: E402

EXIT_OK, EXIT_FAIL, EXIT_USAGE = 0, 1, 2
MAX_SUMMARY_BYTES = 65536
MAX_LINE_CHARS = 200
DEFAULT_MAX_MATCHES = 50
USAGE_KEYS = ("input", "output", "cacheRead", "cacheWrite", "totalTokens")
TOKEN_KEYS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")
SEARCH_SUFFIXES = (".md", ".txt", ".log", ".json", ".jsonl")
UNKNOWN_STATE = "UNKNOWN"
NO_ATTEMPT = "没有 attempt"
SKIPPED_LINKS_LINE = "跳过的链接：%d"
TRANSCRIPT_SUFFIX = ".jsonl"
#: 安全读取（3.0 桌面端 D7）：每页的上限（脱敏之后的字符数）、整份脱敏的文件上限、JSONL 单行的上限（原始字节）
SAFE_PAGE_CHARS = 256 * 1024
SAFE_MAX_TEXT_BYTES = 64 * 1024 * 1024
SAFE_MAX_LINE_BYTES = 4 * 1024 * 1024
#: 分页的成本：一条隐藏的行按多少个字符计；每条显示的行另加多少个字符的开销（免得一页塞进无数个空行或占位）
HIDDEN_LINE_COST = 32
LINE_OVERHEAD = 16
#: JSONL 游标核对的窗口：游标之前这么多字节的哈希（只增长时不变；原地改写会变）
CURSOR_WINDOW = 4096


class LogsError(Exception):
    """命令级错误：一行 `ERROR: …` 到 stderr，按 code 退出，不输出堆栈。"""

    def __init__(self, message: str, code: int = EXIT_FAIL) -> None:
        super().__init__(message)
        self.code = code


class _Missing:
    """usage 里缺失的键：与 JSON 的 null 区分开（比较时用 json.dumps 的文本）。"""

    def __repr__(self) -> str:  # pragma: no cover - 只用于比较，不打印
        return "<missing>"


MISSING = _Missing()


# ---------------------------------------------------------------------------
# 文件系统小工具：只读、逐级查链接、异常不冒出
# ---------------------------------------------------------------------------

class LinkTally:
    """本命令访问过程中遇到的链接条目数（每个条目计一次）。"""

    __slots__ = ("count",)

    def __init__(self) -> None:
        self.count = 0

    def hit(self) -> None:
        self.count += 1


def _is_link(path: Any) -> bool:
    """只通过 pi_dispatch 判断链接；判断不了的条目按普通条目对待（随后 lstat 也会失败）。"""
    try:
        return bool(pd.is_link_or_junction(path))
    except (OSError, ValueError):
        return False


def _exists(path: Any) -> bool:
    try:
        return os.path.exists(path)
    except (OSError, ValueError):
        return False


def _is_dir(path: Any) -> bool:
    try:
        return stat.S_ISDIR(os.lstat(path).st_mode)
    except (OSError, ValueError):
        return False


def _is_regular(path: Any) -> bool:
    try:
        return stat.S_ISREG(os.lstat(path).st_mode)
    except (OSError, ValueError):
        return False


def _scan(directory: Any) -> Optional[List[Tuple[str, Path]]]:
    """目录的直接子项 (名字, 路径)，按名字排序；列不出来时返回 None。

    列不出来按层处理（B11(a)）：由调用方决定是退出码 1、退出码 2 还是跳过，这里不替它决定。
    """
    try:
        with os.scandir(str(directory)) as entries:
            found = [(entry.name, Path(entry.path)) for entry in entries]
    except (OSError, ValueError):
        return None
    found.sort(key=lambda item: item[0])
    return found


def _under(root: Path, parts: Sequence[str]) -> Path:
    """root 之下按段拼接（段里不含分隔符，所以字符串拼接不会二义）。"""
    text = str(root)
    for part in parts:
        if not text.endswith(("\\", "/")):
            text += os.sep
        text += part
    return Path(text)


def _read_json(path: Any) -> Any:
    """UTF-8 JSON；缺失、不可读、不是合法 UTF-8 或不是 JSON 时返回 None。"""
    raw = _read_head(path, -1)
    if raw is None:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError):
        # RecursionError：深嵌套的 JSON 也是解析失败（B11(c)），不得冒出堆栈。
        return None


def _read_head(path: Any, limit: int) -> Optional[bytes]:
    try:
        with open(str(path), "rb") as handle:
            return handle.read(limit)
    except (OSError, ValueError):
        return None


def _strip_eol(raw: bytes) -> bytes:
    """去掉行尾的一个 \n，再去掉它前面的一个 \r。"""
    if raw.endswith(b"\n"):
        raw = raw[:-1]
    if raw.endswith(b"\r"):
        raw = raw[:-1]
    return raw


# ---------------------------------------------------------------------------
# 枚举（B1）
# ---------------------------------------------------------------------------

def _task_entries(runs: Path, links: LinkTally) -> List[Tuple[str, Path]]:
    """runs 根下名字匹配任务 ID 的非链接目录，按名字升序。"""
    if not _exists(runs):
        return []
    found: List[Tuple[str, Path]] = []
    entries = _scan(runs)
    if entries is None:
        # runs 根存在但列不出来：运行错误（B11(a)），退出码 1 与一行 ERROR。
        raise LogsError("无法列出 %s" % runs, EXIT_FAIL)
    for name, path in entries:
        if not pd.TASK_ID_RE.match(name):
            continue
        if _is_link(path):
            links.hit()
            continue
        if not _is_dir(path):
            continue
        found.append((name, path))
    return found


def _attempt_entries(task_dir: Path, links: LinkTally) -> List[Tuple[str, int, Path]]:
    """任务目录下名字匹配 attempt 目录的非链接目录，按编号整数升序。"""
    found: List[Tuple[str, int, Path]] = []
    entries = _scan(task_dir)
    if entries is None:
        # 任务目录列不出来：跳过它的全部 attempt（B11(a)），不计入跳过的链接。
        return []
    for name, path in entries:
        match = pd.ATTEMPT_DIR_RE.match(name)
        if not match:
            continue
        if _is_link(path):
            links.hit()
            continue
        if not _is_dir(path):
            continue
        found.append((name, int(match.group("n")), path))
    found.sort(key=lambda item: item[1])
    return found


def _attempts_of(runs: Path, task: str, links: LinkTally) -> List[Tuple[str, int, Path]]:
    """一个任务的 attempt；任务目录是链接或不存在时视为没有。"""
    task_dir = runs / task
    if _is_link(task_dir) or not _is_dir(task_dir):
        return []
    return _attempt_entries(task_dir, links)


def _evidence(attempt_dir: Path, links: LinkTally) -> Optional[List[Tuple[str, int]]]:
    """attempt 之下递归枚举的普通文件 [(POSIX 相对路径, 字节数)]，按路径字符串升序。

    attempt 目录本身列不出来时返回 None（B11(a)）：由调用方按层决定——list/search 跳过该 attempt，
    show 的目标 attempt 退出码 2。之下的子目录列不出来只是它自己的内容不计入，同层的其它证据照常计入。
    """
    entries = _scan(attempt_dir)
    if entries is None:
        return None
    found: List[Tuple[str, int]] = []
    pending: List[Tuple[str, List[Tuple[str, Path]]]] = [("", entries)]
    while pending:
        rel, here = pending.pop()
        for name, path in here:
            child = rel + "/" + name if rel else name
            if _is_link(path):
                links.hit()
                continue
            try:
                info = os.lstat(path)
            except (OSError, ValueError):
                continue
            if stat.S_ISDIR(info.st_mode):
                nested = _scan(path)
                if nested is not None:
                    pending.append((child, nested))
            elif stat.S_ISREG(info.st_mode):
                found.append((child, info.st_size))
    found.sort(key=lambda item: item[0])
    return found


# ---------------------------------------------------------------------------
# 状态与摘要（B2、B4）
# ---------------------------------------------------------------------------

def _read_state(attempt_dir: Path) -> Tuple[str, Optional[str]]:
    path = attempt_dir / "state.json"
    if _is_link(path) or not _is_regular(path):
        return UNKNOWN_STATE, None
    data = _read_json(path)
    if not isinstance(data, dict):
        return UNKNOWN_STATE, None
    state = data.get("state")
    at = data.get("at")
    return (state if isinstance(state, str) else UNKNOWN_STATE), (at if isinstance(at, str) else None)


def _summary(attempt_dir: Path) -> Optional[Dict[str, Any]]:
    path = attempt_dir / "summary.md"
    if _is_link(path) or not _is_regular(path):
        return None
    try:
        size = os.lstat(path).st_size
    except (OSError, ValueError):
        return None
    raw = _read_head(path, MAX_SUMMARY_BYTES)
    if raw is None:
        return None
    text = raw.decode("utf-8", "replace")
    return {"bytes": size, "truncated": size > MAX_SUMMARY_BYTES, "text": text}


# ---------------------------------------------------------------------------
# 目标解析（B5）
# ---------------------------------------------------------------------------

def _resolve_target(runs: Path, target: str) -> Tuple[str, str, Path]:
    """TARGET → (任务名, attempt 目录名, attempt 路径)；找不到、越界或含链接时退出码 2。"""
    try:
        task, attempt, path = _resolve_forms(runs, target)
        _check_within_runs(runs, path)
        return task, attempt, path
    except LogsError:
        raise
    except (OSError, ValueError, RuntimeError) as exc:
        raise LogsError("目标不存在或不可读：%s" % exc, EXIT_USAGE)


def _check_within_runs(runs: Path, target: Path) -> None:
    """B5.5 兜底：形式 A、B、C、D 解析出的目标都必须真的位于 runs 之下。

    这一步独立于链接检查：即使 is_link_or_junction 永远返回假，指向 runs 之外的 junction 也要被拒绝。
    """
    try:
        resolved = Path(str(target)).resolve()
        root = runs.resolve()
    except (OSError, ValueError, RuntimeError) as exc:
        raise LogsError("目标无法解析：%s" % exc, EXIT_USAGE)
    if not pd.is_within(resolved, root):
        raise LogsError("目标不在 runs 根之下：%s" % target, EXIT_USAGE)


def _resolve_forms(runs: Path, target: str) -> Tuple[str, str, Path]:
    if "\x00" in target:
        raise LogsError("目标不是合法的 attempt：%r" % target, EXIT_USAGE)
    match = pd.PLAN_KEY_RE.match(target)
    if match:
        return _by_plan_key(runs, match.group("task"), int(match.group("ver")))
    if pd.TASK_ID_RE.match(target):
        return _by_task(runs, target)
    if target.count("/") == 1 and "\\" not in target:
        head, _, tail = target.partition("/")
        if pd.TASK_ID_RE.match(head) and pd.ATTEMPT_DIR_RE.match(tail):
            return _by_task_attempt(runs, head, tail)
    return _by_explicit_path(runs, target)


def _by_plan_key(runs: Path, task: str, version: int) -> Tuple[str, str, Path]:
    """形式 A：meta.json 的 plan_version 等于 N 的 attempt 中编号最大者。"""
    best: Optional[Tuple[str, int, Path]] = None
    for name, number, path in _attempts_of(runs, task, LinkTally()):
        meta = path / "meta.json"
        if _is_link(meta) or not _is_regular(meta):
            continue
        data = _read_json(meta)
        if not isinstance(data, dict):
            continue
        value = data.get("plan_version")
        if isinstance(value, bool) or not isinstance(value, int) or value != version:
            continue
        if best is None or number > best[1]:
            best = (name, number, path)
    if best is None:
        raise LogsError("找不到 %s.v%d 对应的 attempt" % (task, version), EXIT_USAGE)
    return task, best[0], best[2]


def _by_task(runs: Path, task: str) -> Tuple[str, str, Path]:
    """形式 B：编号最大的 attempt；任务目录是链接或没有 attempt 时退出码 2。"""
    entries = _attempts_of(runs, task, LinkTally())
    if not entries:
        raise LogsError("任务 %s 没有 attempt（或不存在、是链接）" % task, EXIT_USAGE)
    name, _number, path = entries[-1]
    return task, name, path


def _by_task_attempt(runs: Path, task: str, attempt: str) -> Tuple[str, str, Path]:
    """形式 C：runs/task/attempt-NNN，中间不能有链接，目标必须是目录。"""
    relative = "%s/%s" % (task, attempt)
    linked = pd.first_link_component(runs, relative)
    if linked is not None:
        raise LogsError("目标经过链接：%s" % linked, EXIT_USAGE)
    target = runs / task / attempt
    if _is_link(target) or not _is_dir(target):
        raise LogsError("目标不是目录：%s" % relative, EXIT_USAGE)
    return task, attempt, target


def _segments(raw: str) -> List[str]:
    """按路径分隔符切段；空段与 `.` 不影响路径含义，忽略；`..` 保留。"""
    text = raw.replace("\\", "\x00").replace("/", "\x00") if os.name == "nt" else raw.replace("/", "\x00")
    return [part for part in text.split("\x00") if part not in ("", ".")]


def _same_prefix(parts: Sequence[str], root_parts: Sequence[str]) -> bool:
    if len(parts) < len(root_parts):
        return False
    for index, expected in enumerate(root_parts):
        actual = parts[index]
        if actual == expected:
            continue
        if os.name == "nt" and actual.lower() == expected.lower():
            continue
        return False
    return True


def _by_explicit_path(runs: Path, target: str) -> Tuple[str, str, Path]:
    """形式 D：显式路径，不做任何规范化，按段栈逐段处理。"""
    raw = target if os.path.isabs(target) else os.path.join(os.getcwd(), target)
    parts = _segments(raw)
    root_parts = _segments(str(runs))
    if not _same_prefix(parts, root_parts):
        raise LogsError("目标不在 runs 根之下：%s" % target, EXIT_USAGE)
    stack: List[str] = []
    for part in parts[len(root_parts):]:
        if part == "..":
            if not stack:
                raise LogsError("目标越出 runs 根：%s" % target, EXIT_USAGE)
            stack.pop()
            continue
        stack.append(part)
        if _is_link(_under(runs, stack)):
            raise LogsError("目标经过链接：%s" % "/".join(stack), EXIT_USAGE)
    if (len(stack) != 2 or not pd.TASK_ID_RE.match(stack[0])
            or not pd.ATTEMPT_DIR_RE.match(stack[1])):
        raise LogsError("目标不是 <任务>/<attempt-NNN>：%s" % target, EXIT_USAGE)
    attempt_dir = _under(runs, stack)
    if _is_link(attempt_dir) or not _is_dir(attempt_dir):
        raise LogsError("目标不是目录：%s" % target, EXIT_USAGE)
    return stack[0], stack[1], attempt_dir


# ---------------------------------------------------------------------------
# 时间解析（B7）
# ---------------------------------------------------------------------------

def _parse_iso(text: Any) -> Optional[datetime]:
    """结尾的 Z 换成 +00:00 后按 fromisoformat 解析；不带时区或解析不了为 None。"""
    if not isinstance(text, str):
        return None
    value = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        moment = datetime.fromisoformat(value)
    except (ValueError, OverflowError):
        return None
    if moment.utcoffset() is None:
        return None
    try:
        return moment.astimezone(timezone.utc)
    except (OverflowError, ValueError):
        # 换算到 UTC 时溢出（例如 0001-01-01T00:30:00+01:00）也是不可用时间（B11(c)）。
        return None


def _cli_time(text: str, option: str) -> datetime:
    moment = _parse_iso(text)
    if moment is None:
        raise LogsError("%s 需要带时区的 ISO 8601 时间（例如 2026-10-17T10:00:00Z）：%r" % (option, text),
                        EXIT_USAGE)
    return moment


def _check_task(task: Optional[str]) -> Optional[str]:
    if task is None:
        return None
    if not pd.TASK_ID_RE.match(task):
        raise LogsError("--task 必须是合法的任务 ID：%r" % task, EXIT_USAGE)
    return task


# ---------------------------------------------------------------------------
# list（B3）
# ---------------------------------------------------------------------------

def _collect_attempts(runs: Path, task: Optional[str], state: Optional[str],
                      links: LinkTally) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for name, task_dir in _task_entries(runs, links):
        if task is not None and name != task:
            continue
        for attempt, _number, attempt_dir in _attempt_entries(task_dir, links):
            state_value, state_at = _read_state(attempt_dir)
            if state is not None and state_value != state:
                continue  # 先过滤再列举：被 --state 过滤掉的 attempt 不扫证据，其中的链接也不计数
            evidence = _evidence(attempt_dir, links)
            if evidence is None:
                # attempt 目录列不出来：跳过该 attempt，不列出也不计入证据（B11(a)）。只列一次，
                # 不先试列再正式列——两次之间目录可能变得列不出来（kit-logs a002 复审）。
                continue
            rows.append({
                "task": name,
                "attempt": attempt,
                "state": state_value,
                "state_at": state_at,
                "evidence_files": len(evidence),
                "evidence_bytes": sum(size for _rel, size in evidence),
                "has_summary": (not _is_link(attempt_dir / "summary.md")
                                and _is_regular(attempt_dir / "summary.md")),
            })
    return rows


def cmd_list(args: argparse.Namespace) -> int:
    repo = _repo(args.repo)
    links = LinkTally()
    rows = _collect_attempts(repo.runs_dir, _check_task(args.task), args.state, links)
    if args.json:
        _emit_json({"attempts": rows, "skipped_links": links.count})
        return EXIT_OK
    if not rows:
        print(NO_ATTEMPT)
    for row in rows:
        print("%s/%s  %s  %s  证据 %d 个文件 / %d 字节  摘要：%s" % (
            row["task"], row["attempt"], row["state"], row["state_at"] or "无状态时间",
            row["evidence_files"], row["evidence_bytes"], "有" if row["has_summary"] else "无"))
    if links.count > 0:
        print(SKIPPED_LINKS_LINE % links.count)
    return EXIT_OK


# ---------------------------------------------------------------------------
# show（B4）
# ---------------------------------------------------------------------------

def cmd_show(args: argparse.Namespace) -> int:
    repo = _repo(args.repo)
    task, attempt, attempt_dir = _resolve_target(repo.runs_dir, args.target)
    links = LinkTally()
    state, state_at = _read_state(attempt_dir)
    summary = _summary(attempt_dir)
    evidence = _evidence(attempt_dir, links)
    if evidence is None:
        # 目标 attempt 的证据目录列不出来：按目标解析失败处理，退出码 2（B11(a)）。
        raise LogsError("无法列出 %s" % attempt_dir, EXIT_USAGE)
    facts = {
        "task": task,
        "attempt": attempt,
        "state": state,
        "state_at": state_at,
        "summary": summary,
        "evidence": [{"path": rel, "bytes": size} for rel, size in evidence],
        "skipped_links": links.count,
    }
    if args.json:
        _emit_json(facts)
        return EXIT_OK
    print("%s/%s  状态 %s  状态时间 %s" % (task, attempt, state, state_at or "无"))
    if summary is None:
        print("摘要：无")
    else:
        print("摘要（%d 字节%s）：" % (summary["bytes"], "，已截断" if summary["truncated"] else ""))
        print(summary["text"])
        if summary["truncated"]:
            print("已截断：只显示前 %d 字节，共 %d 字节" % (MAX_SUMMARY_BYTES, summary["bytes"]))
    print("证据 %d 个文件 / %d 字节：" % (len(evidence), sum(size for _rel, size in evidence)))
    for rel, size in evidence:
        print("  %s  %d 字节" % (rel, size))
    if links.count > 0:
        print(SKIPPED_LINKS_LINE % links.count)
    return EXIT_OK



# ---------------------------------------------------------------------------
# 安全读取（3.0 桌面端 D7；docs/themis-tally-3.0-桌面端.md）
#
# 分页的单位是脱敏之后的文本，不是原始字节：切片里看不到上下文，单独脱敏会漏（r2-B1）。
# - JSONL 逐行先解析：合法的行按键名脱敏（redact_json）后用 json.dumps 的缺省格式写出；解析不了的行、超过
#   SAFE_MAX_LINE_BYTES 的行只给占位，不按没有上下文的文本显示（r3-B1、r4-B1）。
# - .json 整份能解析时按键名脱敏、带缩进写出（保持多行）；其余文本整份 redact_secrets（它遇到确定不了结束的值，
#   会遮掉其余部分）。整份超过 SAFE_MAX_TEXT_BYTES 的不显示。
# - 游标绑定文件的身份：普通文本要求大小、修改时间、文件号都不变；JSONL 要求文件号不变、文件只增长，并核对
#   偏移是原始行首、偏移之前的一段与读到一半的那一行都没变（r3-S3；闸二 D1-A 第 1 轮 B2、B3）。
# - 单行超过一页时按片给出，片与片首尾相接（r3-S4、r4-S1）。
# 这里是纯函数、不缓存：logs cat 是一次性的进程；缓存放在桌面端的本机服务里。
# ---------------------------------------------------------------------------

class StaleCursor(LogsError):
    """游标对应的文件已变化（被替换、截短或改写）：从头读。"""

    def __init__(self) -> None:
        super().__init__("游标对应的文件已变化：请从头读取", EXIT_USAGE)


def safe_mode(rel: str) -> str:
    lower = rel.lower()
    if lower.endswith(".jsonl"):
        return "jsonl"
    if lower.endswith(".json"):
        return "json"
    return "text"


def file_identity(path: Path) -> Tuple[int, int, int]:
    """（大小, 修改时间纳秒, 文件号）。"""
    info = os.lstat(str(path))
    return info.st_size, info.st_mtime_ns, info.st_ino


def _dump(value: Any, indent: Optional[int] = None) -> str:
    """与 pi_dispatch 的写法相同：孤立的代理字符写成 \\uXXXX，免得输出时编码失败。"""
    return pd._SURROGATE_RE.sub(lambda m: chr(92) + "u%04x" % ord(m.group(0)),
                                json.dumps(value, ensure_ascii=False, indent=indent))


def redacted_text(path: Path, mode: str) -> str:
    """整份读出并脱敏（json 与 text 模式）。超过上限、读不出来都抛 LogsError（退出码 2）。

    最多读上限加 1 字节：先查大小再读，中间文件变大就能绕过上限（闸二 D1-A 第 1 轮 S1）。"""
    raw = _read_head(path, SAFE_MAX_TEXT_BYTES + 1)
    if raw is None:
        raise LogsError("读不出来：%s" % path.name, EXIT_USAGE)
    if len(raw) > SAFE_MAX_TEXT_BYTES:
        raise LogsError("文件太大（超过上限 %d 字节），不在这里显示；请直接查看文件" % SAFE_MAX_TEXT_BYTES, EXIT_USAGE)
    text = raw.decode("utf-8", "replace")
    if mode == "json":
        try:
            return _dump(pd.redact_json(json.loads(text)), indent=2) + "\n"
        except (ValueError, RecursionError):
            pass  # 不是合法的 JSON（或嵌套太深）：按文本整份脱敏
    return pd.redact_secrets(text)


def _jsonl_records(path: Path, start: int, final: bool):
    """从原始偏移 start 起逐行读：yield (行起点, 下一行起点, 行内容或 None)，None 表示这一行超过上限。

    每次最多读 SAFE_MAX_LINE_BYTES + 1 字节，超长的行只计长度、不留内容，内存有上限。最后一行没有换行时：
    final 为真才算写完，否则不给（跟随时它可能还在写）。"""
    limit = SAFE_MAX_LINE_BYTES
    with open(str(path), "rb") as handle:
        handle.seek(start)
        offset = start
        while True:
            line, length, too_long, ended = b"", 0, False, False
            while True:
                piece = handle.readline(limit + 1)
                if not piece:
                    break
                length += len(piece)
                if not too_long:
                    line += piece
                    if len(_strip_eol(line)) > limit:
                        too_long, line = True, b""
                if piece.endswith(b"\n"):
                    ended = True
                    break
            if length == 0 or (not ended and not final):
                return
            yield offset, offset + length, (None if too_long else _strip_eol(line))
            offset += length


def _jsonl_entry(raw: Optional[bytes]) -> Dict[str, Any]:
    """一行 JSONL 的显示：{"text": …} 或 {"hidden": "too_long" | "not_json"}。"""
    if raw is None:
        return {"hidden": "too_long"}
    line = raw.decode("utf-8", "replace")
    if not line.strip():
        return {"text": ""}
    try:
        return {"text": _dump(pd.redact_json(json.loads(line)))}
    except (ValueError, RecursionError):
        return {"hidden": "not_json"}


def _cursor(kind: str, *fields: Any) -> str:
    return ":".join([kind] + [("%d" % field) if isinstance(field, int) else field for field in fields])


def _cursor_fields(cursor: str, kind: str, count: int) -> List[str]:
    parts = cursor.split(":")
    if len(parts) != count + 1 or parts[0] != kind or not all(re.fullmatch(r"[0-9a-f]{1,64}", part)
                                                                 for part in parts[1:]):
        raise LogsError("游标格式不对（游标只能原样带回）", EXIT_USAGE)
    return parts[1:]


def _decimal(field: str) -> int:
    if not field.isdigit():
        raise LogsError("游标格式不对（游标只能原样带回）", EXIT_USAGE)
    return int(field)


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def _window(path: Path, position: int) -> bytes:
    """游标之前的一段原始字节（最多 CURSOR_WINDOW）。"""
    start = max(0, position - CURSOR_WINDOW)
    with open(str(path), "rb") as handle:
        handle.seek(start)
        return handle.read(position - start)


def _lines_before(path: Path, position: int) -> int:
    """偏移之前有多少个换行：行号由文件本身数出来，不信游标里的值。"""
    count, remaining = 0, position
    with open(str(path), "rb") as handle:
        while remaining > 0:
            chunk = handle.read(min(1 << 20, remaining))
            if not chunk:
                break
            count += chunk.count(b"\n")
            remaining -= len(chunk)
    return count


def _text_page(path: Path, rel: str, mode: str, cursor: Optional[str], limit: int) -> Dict[str, Any]:
    size, mtime, ino = file_identity(path)
    offset = 0
    if cursor is not None:
        offset, c_size, c_mtime, c_ino = [_decimal(field) for field in _cursor_fields(cursor, "t", 4)]
        if (c_size, c_mtime, c_ino) != (size, mtime, ino):
            raise StaleCursor()
    text = redacted_text(path, mode)
    if offset > len(text):
        raise StaleCursor()
    if offset + limit >= len(text):
        piece, after = text[offset:], len(text)
    else:
        window = text[offset:offset + limit]
        cut = window.rfind("\n")
        piece, after = (window[:cut + 1], offset + cut + 1) if cut >= 0 else (window, offset + limit)
    page: Dict[str, Any] = {"path": rel, "mode": "text", "text": piece,
                            "next_cursor": _cursor("t", after, size, mtime, ino), "done": after >= len(text)}
    line_start = text.rfind("\n", 0, offset) + 1
    line_end = text.find("\n", line_start)
    line_end = len(text) if line_end < 0 else line_end
    # 从一行的内容中间开始（停在行尾的换行上不算，闸二 D1-A 第 1 轮 N1），或在一行的中间结束
    if line_start < offset < line_end or (not piece.endswith("\n") and after < len(text)):
        # 这一页的第一行是长行的一片：标明第几片、共几片（片从行首起每 limit 个字符一片）
        page["part"] = (offset - line_start) // limit + 1
        page["parts"] = max(page["part"], -(-(line_end - line_start) // limit))
    return page


def _jsonl_resume(path: Path, cursor: str, size: int, mtime: int, ino: int, final: bool) -> Tuple[int, int]:
    """核对 JSONL 游标，返回（原始偏移, 行内字符位置）。不成立就抛 StaleCursor（闸二 D1-A 第 1 轮 B2、B3）：
    - 文件号要相同，文件只能变长；长度不变而修改时间变了，就是原地改写；
    - 偏移必须是原始行首（前一个字节是换行）：否则后半截可能成了合法的 JSON，把本该隐藏的行漏出来；
      文件没变时停在末尾的游标除外（最后一行没有换行，读完之后什么也不会再给）；
    - 偏移之前的一段（CURSOR_WINDOW）要与发出游标时相同；读到一行中间时，这一行也要与当时相同。
    更早的位置被改写、同时文件又变长，查不出来（证据目录按规定只读；同账户进程不在防护范围，设计 D4）。"""
    fields = _cursor_fields(cursor, "j", 7)
    position, char, c_ino, c_size, c_mtime = [_decimal(field) for field in fields[:5]]
    window_digest, line_digest = fields[5], fields[6]
    if c_ino != ino or size < c_size or position > size or (size == c_size and mtime != c_mtime):
        raise StaleCursor()
    window = _window(path, position)
    unchanged_end = position == size == c_size
    if (position > 0 and not window.endswith(b"\n") and not unchanged_end) or _digest(window) != window_digest:
        raise StaleCursor()
    if char:
        record = next(iter(_jsonl_records(path, position, final)), None)
        if record is None or record[2] is None or _digest(record[2]) != line_digest:
            raise StaleCursor()
    return position, char


def _jsonl_cursor(path: Path, position: int, char: int, line: Optional[bytes], size: int, mtime: int,
                  ino: int) -> str:
    return _cursor("j", position, char, ino, size, mtime, _digest(_window(path, position)),
                   _digest(line) if char and line is not None else "0")


def _jsonl_page(path: Path, rel: str, cursor: Optional[str], limit: int, final: bool) -> Dict[str, Any]:
    size, mtime, ino = file_identity(path)
    position, char = (0, 0) if cursor is None else _jsonl_resume(path, cursor, size, mtime, ino, final)
    number = _lines_before(path, position) + 1
    lines: List[Dict[str, Any]] = []
    used = 0
    after, after_char, after_line = position, char, None
    for start, end, raw in _jsonl_records(path, position, final):
        entry = _jsonl_entry(raw)
        body = entry.get("text")
        if body is not None and (char or len(body) > limit):
            if lines:
                break  # 先交出已有的行；下一页从这条长行开始
            if char > len(body):
                raise StaleCursor()
            lines.append({"n": number, "text": body[char:char + limit], "part": char // limit + 1,
                          "parts": -(-len(body) // limit)})
            if char + limit < len(body):
                after, after_char, after_line = start, char + limit, raw
            else:
                after, after_char = end, 0
            break
        cost = len(body) + LINE_OVERHEAD if body is not None else HIDDEN_LINE_COST
        if lines and used + cost > limit:
            break
        lines.append(dict({"n": number}, **entry))
        used += cost
        number += 1
        after, after_char = end, 0
    return {"path": rel, "mode": "jsonl", "lines": lines,
            "next_cursor": _jsonl_cursor(path, after, after_char, after_line, size, mtime, ino),
            "done": after >= size and after_char == 0}


def safe_page(path: Path, rel: str, cursor: Optional[str] = None, limit: int = SAFE_PAGE_CHARS,
              final: bool = True) -> Dict[str, Any]:
    """按页读一个证据文件（脱敏之后的文本）。text 模式返回 {path, mode, text, part?, parts?, next_cursor, done}；
    jsonl 模式返回 {path, mode, lines, next_cursor, done}。final 为假时，JSONL 最后一行没有换行就不给（跟随用）。"""
    if not 1 <= limit <= SAFE_PAGE_CHARS:
        raise LogsError("--limit 必须在 1 到 %d 之间：%d" % (SAFE_PAGE_CHARS, limit), EXIT_USAGE)
    try:
        if safe_mode(rel) == "jsonl":
            return _jsonl_page(path, rel, cursor, limit, final)
        return _text_page(path, rel, safe_mode(rel), cursor, limit)
    except (OSError, ValueError) as exc:
        raise LogsError("读不出来：%s" % exc, EXIT_USAGE)


def safe_lines(path: Path, rel: str):
    """搜索用：脱敏之后的 (行号, 文本)，隐藏的行不给。text、json 模式整份超过上限时抛 LogsError。

    每一行都先脱敏：不能用原文预筛——带分支的正则（`猜的值|<redacted>`）会让返回与否取决于原文，成了猜值的
    通道（闸二 D1-A 第 1 轮 B1）。"""
    if safe_mode(rel) == "jsonl":
        number = 0
        for _start, _end, raw in _jsonl_records(path, 0, True):
            number += 1
            if raw is None:
                continue
            entry = _jsonl_entry(raw)
            if "text" in entry:
                yield number, entry["text"]
        return
    for number, line in enumerate(redacted_text(path, safe_mode(rel)).split("\n"), 1):
        yield number, line[:-1] if line.endswith("\r") else line


# ---------------------------------------------------------------------------
# cat（3.0 桌面端 D13）
# ---------------------------------------------------------------------------

def cmd_cat(args: argparse.Namespace) -> int:
    repo = _repo(args.repo)
    task, attempt, attempt_dir = _resolve_target(repo.runs_dir, args.target)
    links = LinkTally()
    evidence = _evidence(attempt_dir, links)
    if evidence is None:
        raise LogsError("无法列出 %s" % attempt_dir, EXIT_USAGE)
    rel = args.path.replace(chr(92), "/")
    if rel not in {item for item, _size in evidence}:
        # 只认证据清单里的相对路径：清单本身不含链接、不出 attempt 目录（B5、B11）
        raise LogsError("不在 %s/%s 的证据清单里：%s" % (task, attempt, rel), EXIT_USAGE)
    page = safe_page(_under(attempt_dir, rel.split("/")), rel, args.cursor, args.limit)
    if args.json:
        _emit_json(page)
        return EXIT_OK
    if page["mode"] == "text":
        sys.stdout.write(page["text"])
    else:
        for line in page["lines"]:
            print(line["text"] if "text" in line else "（第 %d 行已隐藏：%s）" % (
                line["n"], "不是合法 JSON" if line["hidden"] == "not_json" else "超过 %d 字节" % SAFE_MAX_LINE_BYTES))
    if not page["done"]:
        print("（未完：--cursor %s）" % page["next_cursor"], file=sys.stderr)
    return EXIT_OK


# ---------------------------------------------------------------------------
# search（B6；3.0 桌面端起在脱敏之后的文本里搜，r3-B1）
# ---------------------------------------------------------------------------

def _iter_lines(path: Path):
    """逐行读取：UTF-8 解码（errors=replace），去掉行尾的 \n 与 \r。读不出来就没有行。"""
    try:
        with open(str(path), "rb") as handle:
            for raw in handle:
                yield _strip_eol(raw).decode("utf-8", "replace")
    except (OSError, ValueError):
        return


#: logs search 的 PATTERN（第 58 轮）：只做逐行匹配，反向引用与条件分组拒绝；括号嵌套设上限。
#: 迁移到 TS 时，“这一行有没有匹配”要与 Python 逐字一致：反向引用（组没参与匹配时 Python 判失败、JS 当空串；
#: 迭代之间捕获的重置也不同）与条件分组 JS 复现不了；嵌套太深时 Python 的 RecursionError 取决于当时的栈深。
SEARCH_MAX_NESTING = 100
SEARCH_NO_REFS = "PATTERN 不支持反向引用与条件分组（logs search 只做逐行匹配）"
SEARCH_TOO_DEEP = "PATTERN 的括号嵌套超过 %d 层" % SEARCH_MAX_NESTING


def _paren_depth(pattern: str) -> int:
    """PATTERN 里括号的最大嵌套层数，按字面计：反斜杠转义的下一个字符不算，字符类 [...] 里的不算（类开头的 ^ 之后
    紧跟的 ] 是字面量）。只计数，不判断正则合不合法；(?x) 注释里的括号也算。"""
    depth = deepest = index = 0
    in_class = False
    while index < len(pattern):
        char = pattern[index]
        if char == "\\":
            index += 2
            continue
        if in_class:
            in_class = char != "]"
        elif char == "[":
            in_class = True
            index += 1
            if index < len(pattern) and pattern[index] == "^":
                index += 1
            if index < len(pattern) and pattern[index] == "]":
                index += 1
            continue
        elif char == "(":
            depth += 1
            deepest = max(deepest, depth)
        elif char == ")":
            depth = max(0, depth - 1)
        index += 1
    return deepest


def _uses_refs(node: Any) -> bool:
    """语法树里有没有 GROUPREF（\\1、(?P=name)）或 GROUPREF_EXISTS（(?(id)yes|no)）。"""
    if isinstance(node, _re_parser.SubPattern):
        return any(op in (_re_constants.GROUPREF, _re_constants.GROUPREF_EXISTS) or _uses_refs(av)
                   for op, av in node.data)
    if isinstance(node, (list, tuple)):
        return any(_uses_refs(item) for item in node)
    return False


def cmd_search(args: argparse.Namespace) -> int:
    repo = _repo(args.repo)
    try:
        if _paren_depth(args.pattern) > SEARCH_MAX_NESTING:
            raise LogsError(SEARCH_TOO_DEEP, EXIT_USAGE)
        with warnings.catch_warnings():
            # re 对 [[、--、&& 等写法发的 FutureWarning（以及 DeprecationWarning）带着调用方的文件与源码行，
            # 同一个 PATTERN 还会在 parse、compile 各发一次：stderr 里是噪音，TS 版也写不出一样的字节（第 58 轮）
            warnings.simplefilter("ignore")
            if _uses_refs(_re_parser.parse(args.pattern)):
                raise LogsError(SEARCH_NO_REFS, EXIT_USAGE)
            pattern = re.compile(args.pattern)
    except (re.error, OverflowError, RecursionError) as exc:
        # 溢出与深嵌套的正则同样是编译失败（B11(c)）：用法错误，退出码 2。
        raise LogsError("PATTERN 不是合法的正则表达式：%s" % exc, EXIT_USAGE)
    if args.max < 1:
        raise LogsError("--max 必须是不小于 1 的整数：%d" % args.max, EXIT_USAGE)
    task = _check_task(args.task)
    links = LinkTally()
    matches: List[Dict[str, Any]] = []
    truncated = False
    skipped_large = 0
    for name, task_dir in _task_entries(repo.runs_dir, links):
        if task is not None and name != task:
            continue
        for attempt, _number, attempt_dir in _attempt_entries(task_dir, links):
            evidence = _evidence(attempt_dir, links)
            if evidence is None:
                # attempt 目录列不出来：跳过该 attempt（B11(a)）。
                continue
            for rel, _size in evidence:
                if not rel.endswith(SEARCH_SUFFIXES):
                    continue
                try:
                    # 在脱敏之后的文本里搜（3.0 桌面端 r3-B1）：摘录只来自脱敏之后的文本，隐藏的行不参加
                    for number, text in safe_lines(attempt_dir / rel, rel):
                        if not pattern.search(text):
                            continue
                        if len(matches) >= args.max:
                            truncated = True
                            break
                        matches.append({"task": name, "attempt": attempt, "path": rel, "line": number,
                                        "text": text[:MAX_LINE_CHARS]})
                except LogsError:
                    skipped_large += 1  # 太大或读不出来：不搜，计数
                except OSError:
                    pass  # 读不出来的文件没有行（与旧行为相同）
                if truncated:
                    break
            if truncated:
                break
        if truncated:
            break
    if args.json:
        _emit_json({"matches": matches, "truncated": truncated, "skipped_links": links.count,
                    "skipped_large": skipped_large})
        return EXIT_OK
    for match in matches:
        print("%s/%s/%s:%d: %s" % (match["task"], match["attempt"], match["path"], match["line"], match["text"]))
    if truncated:
        print("（已截断：只显示前 %d 条匹配）" % args.max)
    if links.count > 0:
        print(SKIPPED_LINKS_LINE % links.count)
    if skipped_large > 0:
        print("跳过的大文件或读不出来的文件：%d" % skipped_large)
    return EXIT_OK


# ---------------------------------------------------------------------------
# usage：执行端（B7.1）
# ---------------------------------------------------------------------------

def _executor_row(attempt_dir: Path, links: LinkTally) -> Tuple[str, Optional[str], Optional[Dict[str, int]]]:
    """(状态, requested_model, usage)。unknown 时 usage 为 None，不计入任何合计。"""
    path = attempt_dir / "events-summary.json"
    if _is_link(path):
        links.hit()
        return "unknown", None, None
    if not _is_regular(path):
        return "unknown", None, None
    data = _read_json(path)
    if not isinstance(data, dict):
        return "unknown", None, None
    requested = data.get("requested_model")
    model = None
    if isinstance(requested, dict):
        provider, name = requested.get("provider"), requested.get("model")
        if isinstance(provider, str) and isinstance(name, str):
            model = "%s/%s" % (provider, name)
    usage = data.get("usage")
    if not isinstance(usage, dict):
        return "unknown", model, None
    values: Dict[str, int] = {}
    for key in USAGE_KEYS:
        value = usage.get(key)
        if isinstance(value, bool) or not isinstance(value, int):
            return "unknown", model, None
        values[key] = value
    if (data.get("complete") is not True or data.get("truncated") is True
            or not (isinstance(data.get("parse_error_lines"), list) and not data.get("parse_error_lines"))):
        return "partial", model, values
    return "known", model, values


def _zero_usage() -> Dict[str, int]:
    return {key: 0 for key in USAGE_KEYS}


def _add_usage(target: Dict[str, int], values: Dict[str, int]) -> None:
    for key in USAGE_KEYS:
        target[key] += values[key]


def _executor_stats(runs: Path, task: Optional[str]) -> Dict[str, Any]:
    links = LinkTally()
    attempts: List[Dict[str, Any]] = []
    totals = _zero_usage()
    counts = {"known": 0, "partial": 0, "unknown": 0}
    groups: Dict[Optional[str], Dict[str, Any]] = {}
    for name, task_dir in _task_entries(runs, links):
        if task is not None and name != task:
            continue
        for attempt, _number, attempt_dir in _attempt_entries(task_dir, links):
            status, model, values = _executor_row(attempt_dir, links)
            counts[status] += 1
            if values is not None:
                _add_usage(totals, values)
            attempts.append({"task": name, "attempt": attempt, "requested_model": model,
                             "status": status, "usage": dict(values) if values is not None else None})
            group = groups.get(model)
            if group is None:
                group = groups[model] = {"requested_model": model, "known": 0, "partial": 0, "unknown": 0,
                                         "usage": _zero_usage()}
            group[status] += 1
            if values is not None:
                _add_usage(group["usage"], values)
    by_model = sorted(groups.values(), key=lambda group: (group["requested_model"] is not None,
                                                          group["requested_model"] or ""))
    return {"attempts": attempts, "totals": totals, "counts": counts, "by_model": by_model,
            "skipped_links": links.count}


# ---------------------------------------------------------------------------
# usage：规划端（B7.2）
# ---------------------------------------------------------------------------

class _Record:
    """一条候选会话记录的规范值（只取合同允许的字段）。"""

    __slots__ = ("identifier", "final", "counts", "model", "sidechain", "time")

    def __init__(self, identifier: str, final: bool, counts: Tuple[Any, ...], model: Optional[str],
                 sidechain: bool, time: Optional[datetime]) -> None:
        self.identifier = identifier
        self.final = final
        self.counts = counts
        self.model = model
        self.sidechain = sidechain
        self.time = time


def _canonical(value: Any) -> Any:
    """计数按 json.dumps 的文本比较（1 与 1.0 不同，null 与缺失不同）。"""
    if value is MISSING:
        return (True, None)
    return (False, json.dumps(value, sort_keys=True, ensure_ascii=False))


def _classify(raw: bytes) -> Tuple[Optional[str], Optional[_Record]]:
    """一行 → (跳过原因, 记录)。空行与只含空白的行返回 (None, None) 且不计入任何计数。"""
    line = _strip_eol(raw)
    if not line.strip():
        return None, None
    try:
        text = line.decode("utf-8")
    except UnicodeDecodeError:
        return "bad_json", None
    try:
        obj = json.loads(text)
    except (ValueError, RecursionError):
        # 深嵌套的一行同样是坏行（B11(c)）。
        return "bad_json", None
    if not isinstance(obj, dict):
        return "not_object", None
    message = obj.get("message")
    if not isinstance(message, dict):
        return "not_candidate", None
    identifier = message.get("id")
    if not isinstance(identifier, str) or not identifier:
        return "not_candidate", None
    usage = message.get("usage")
    if not isinstance(usage, dict):
        return "not_candidate", None
    stop = message.get("stop_reason")
    final = isinstance(stop, str) and stop != ""
    counts = tuple(usage.get(key, MISSING) for key in TOKEN_KEYS)
    model = message.get("model")
    return None, _Record(identifier, final, counts, model if isinstance(model, str) else None,
                         obj.get("isSidechain") is True, _parse_iso(obj.get("timestamp")))


def _read_transcript(path: Path, groups: Dict[str, List[_Record]], skipped: Dict[str, int]) -> bool:
    """读一个会话记录文件；读不出来时整个文件都不计入，返回 False。"""
    try:
        with open(str(path), "rb") as handle:
            raw_lines = handle.readlines()
    except (OSError, ValueError):
        return False
    local: Dict[str, int] = {"bad_json": 0, "not_object": 0, "not_candidate": 0}
    pending: Dict[str, List[_Record]] = {}
    for raw in raw_lines:
        reason, record = _classify(raw)
        if reason is not None:
            local[reason] += 1
        elif record is not None:
            pending.setdefault(record.identifier, []).append(record)
    for key, value in local.items():
        skipped[key] += value
    for identifier, records in pending.items():
        groups.setdefault(identifier, []).extend(records)
    return True


def _transcript_files(path: Path, planner: Dict[str, int]) -> Optional[List[Path]]:
    """一个 --transcript 参数要读的文件：目录只取直接一层 .jsonl，否则读路径本身。

    目录列不出来时返回 None（B11(b)）：调用方把 unreadable_files 加 1 并继续下一个参数。
    """
    if os.path.isdir(str(path)):
        entries = _scan(path)
        if entries is None:
            return None
        found: List[Path] = []
        for name, child in entries:
            if not name.endswith(TRANSCRIPT_SUFFIX):
                continue
            if _is_link(child):
                planner["skipped_links"] += 1
                continue
            if not _is_regular(child):
                continue
            found.append(child)
        return found
    return [path]


def _planner_stats(paths: Sequence[str], since: Optional[datetime], until: Optional[datetime]) -> Dict[str, Any]:
    stats: Dict[str, Any] = {
        "lower_bound": True,
        "partial": False,
        "included_messages": 0,
        "by_model": [],
        "skipped_lines": {"bad_json": 0, "not_object": 0, "not_candidate": 0},
        "skipped_links": 0,
        "unreadable_files": 0,
        "duplicate_records": 0,
        "conflict_ids": 0,
        "conflict_records": 0,
        "incomplete_ids": 0,
        "intermediate_records": 0,
        "unusable_timestamps": 0,
        "ids_without_time": 0,
        "outside_window_ids": 0,
        "non_integer_fields": 0,
    }
    groups: Dict[str, List[_Record]] = {}
    for text in paths:
        target = Path(text)
        files = _transcript_files(target, stats)
        if files is None:
            # 目录型参数列不出来：不中止，计入不可读文件并标部分（B11(b)）。
            stats["unreadable_files"] += 1
            continue
        for path in files:
            if not _read_transcript(path, groups, stats["skipped_lines"]):
                stats["unreadable_files"] += 1
    by_model: Dict[Tuple[Optional[str], bool], Dict[str, Any]] = {}
    for identifier in sorted(groups):
        records = groups[identifier]
        finals = [record for record in records if record.final]
        stats["intermediate_records"] += len(records) - len(finals)
        stats["unusable_timestamps"] += sum(1 for record in records if record.time is None)
        if _conflicted(records, finals):
            stats["conflict_ids"] += 1
            stats["conflict_records"] += len(records)
            continue
        if not finals:
            stats["incomplete_ids"] += 1
            continue
        stats["duplicate_records"] += len(finals) - 1
        times = [record.time for record in records if record.time is not None]
        if not times:
            stats["ids_without_time"] += 1
            continue
        moment = min(times)
        if since is not None and moment < since:
            stats["outside_window_ids"] += 1
            continue
        if until is not None and moment >= until:
            stats["outside_window_ids"] += 1
            continue
        stats["included_messages"] += 1
        key = (finals[0].model, finals[0].sidechain)
        row = by_model.get(key)
        if row is None:
            row = by_model[key] = {"model": key[0], "sidechain": key[1], "messages": 0,
                                   **{name: 0 for name in TOKEN_KEYS}}
        row["messages"] += 1
        for name, value in zip(TOKEN_KEYS, finals[0].counts):
            if isinstance(value, bool) or not isinstance(value, int):
                stats["non_integer_fields"] += 1
            else:
                row[name] += value
    stats["by_model"] = [by_model[key] for key in sorted(
        by_model, key=lambda item: (item[0] is not None, item[0] or "", item[1]))]
    stats["partial"] = bool(stats["conflict_ids"] or stats["incomplete_ids"] or stats["unreadable_files"])
    return stats


def _conflicted(records: List[_Record], finals: List[_Record]) -> bool:
    """组内任意两条记录的 model 或 sidechain 不同；或最终记录之间四个计数字段任一不同。"""
    for index, record in enumerate(records):
        for other in records[index + 1:]:
            if record.model != other.model or record.sidechain != other.sidechain:
                return True
    for index, record in enumerate(finals):
        for other in finals[index + 1:]:
            if any(_canonical(a) != _canonical(b) for a, b in zip(record.counts, other.counts)):
                return True
    return False


def cmd_usage(args: argparse.Namespace) -> int:
    repo = _repo(args.repo)
    task = _check_task(args.task)
    since = _cli_time(args.since, "--since") if args.since is not None else None
    until = _cli_time(args.until, "--until") if args.until is not None else None
    if since is not None and until is not None and since > until:
        raise LogsError("--since 晚于 --until", EXIT_USAGE)
    transcripts = list(args.transcript or [])
    for text in transcripts:
        if not _exists(text):
            raise LogsError("--transcript 路径不存在：%s" % text, EXIT_USAGE)
    executor = _executor_stats(repo.runs_dir, task)
    planner = _planner_stats(transcripts, since, until) if transcripts else None
    if args.json:
        _emit_json({"executor": executor, "planner": planner})
        return EXIT_OK
    print("执行端：attempt %d 个 · known %d · partial %d · unknown %d · 跳过的链接 %d" % (
        len(executor["attempts"]), executor["counts"]["known"], executor["counts"]["partial"],
        executor["counts"]["unknown"], executor["skipped_links"]))
    for row in executor["attempts"]:
        if row["usage"] is None:
            detail = "unknown（没有可用的 usage）"
        else:
            detail = "%s  input=%d output=%d cacheRead=%d cacheWrite=%d totalTokens=%d" % (
                row["status"], row["usage"]["input"], row["usage"]["output"], row["usage"]["cacheRead"],
                row["usage"]["cacheWrite"], row["usage"]["totalTokens"])
        print("  %s/%s  %s  %s" % (row["task"], row["attempt"], row["requested_model"] or "（无模型）", detail))
    print("  合计 input=%d output=%d cacheRead=%d cacheWrite=%d totalTokens=%d" % (
        executor["totals"]["input"], executor["totals"]["output"], executor["totals"]["cacheRead"],
        executor["totals"]["cacheWrite"], executor["totals"]["totalTokens"]))
    print("  按模型：")
    for group in executor["by_model"]:
        print("    %s  known=%d partial=%d unknown=%d  input=%d output=%d cacheRead=%d cacheWrite=%d "
              "totalTokens=%d" % (group["requested_model"] or "（无模型）", group["known"], group["partial"],
                                  group["unknown"], group["usage"]["input"], group["usage"]["output"],
                                  group["usage"]["cacheRead"], group["usage"]["cacheWrite"],
                                  group["usage"]["totalTokens"]))
    if planner is None:
        print("规划端：未给 --transcript，未统计规划端")
        return EXIT_OK
    skipped = planner["skipped_lines"]
    print("规划端（下界：只统计命令行给出的会话记录，只数会话记录里有的调用）%s：计入消息 %d · 重复最终记录 %d · "
          "中间记录 %d" % ("，部分（有冲突、未完成或读不出的文件）" if planner["partial"] else "",
                           planner["included_messages"], planner["duplicate_records"],
                           planner["intermediate_records"]))
    print("  冲突 %d 组 / %d 条 · 未完成 %d 组 · 无可用时间 %d · 窗口外 %d · 非整数字段 %d · 不可读文件 %d · "
          "跳过的链接 %d" % (planner["conflict_ids"], planner["conflict_records"], planner["incomplete_ids"],
                            planner["ids_without_time"], planner["outside_window_ids"],
                            planner["non_integer_fields"], planner["unreadable_files"],
                            planner["skipped_links"]))
    print("  坏行 %d · 不是对象 %d · 不是候选记录 %d · 不可用时间戳 %d" % (
        skipped["bad_json"], skipped["not_object"], skipped["not_candidate"], planner["unusable_timestamps"]))
    print("  按模型：")
    for row in planner["by_model"]:
        print("    %s  %s  messages=%d  input_tokens=%d cache_creation_input_tokens=%d "
              "cache_read_input_tokens=%d output_tokens=%d" % (
                  row["model"] or "（无模型）", "子代理" if row["sidechain"] else "主线", row["messages"],
                  row["input_tokens"], row["cache_creation_input_tokens"], row["cache_read_input_tokens"],
                  row["output_tokens"]))
    return EXIT_OK


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def _repo(path: Optional[str]) -> Any:
    try:
        return pd.Repo.discover(path)
    except pd.DispatchError as exc:
        raise LogsError(str(exc), exc.code)


def _emit_json(obj: Any) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kit_logs.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", help="仓库路径（默认当前目录）")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("list", help="attempt 清单：状态、证据文件数与字节数、有没有摘要")
    p.add_argument("--task", help="只看这个任务")
    p.add_argument("--state", help="按状态字符串完全相等过滤")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("show", help="一个 attempt 的状态、摘要与证据清单")
    p.add_argument("target", help="task.vN、task、task/attempt-NNN 或显式路径")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("search", help="在证据的 .md/.txt/.log/.json/.jsonl 里搜索（脱敏之后的文本）")
    p.add_argument("pattern", help="Python re 语法")
    p.add_argument("--task", help="只搜这个任务")
    p.add_argument("--max", type=int, default=DEFAULT_MAX_MATCHES, help="最多输出多少条匹配（默认 50）")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("cat", help="按页读一个证据文件：分页的单位是脱敏之后的文本，游标原样带回")
    p.add_argument("target", help="task.vN、task、task/attempt-NNN 或显式路径")
    p.add_argument("path", help="证据清单里的相对路径（logs show 列出的那些）")
    p.add_argument("--cursor", help="上一页给出的 next_cursor")
    p.add_argument("--limit", type=int, default=SAFE_PAGE_CHARS, help="每页最多多少个字符（默认 %d）" % SAFE_PAGE_CHARS)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_cat)

    p = sub.add_parser("usage", help="执行端与规划端的 token 用量（下界）")
    p.add_argument("--task", help="只统计这个任务的执行端 attempt")
    p.add_argument("--transcript", action="append", help="会话记录文件或目录，可重复给出")
    p.add_argument("--since", help="只统计代表时间不早于它的消息（含）")
    p.add_argument("--until", help="只统计代表时间早于它的消息（不含）")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_usage)
    return pd.no_abbrev(parser)  # 长选项不接受缩写（与调度器相同，3.0 第二轮）


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
    try:
        return int(args.func(args))
    except LogsError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return exc.code
    except (RecursionError, OverflowError) as exc:
        # 最后一道防线（B11(c)）：任何路径都只留一行 ERROR，不冒堆栈。
        print("ERROR: %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return EXIT_FAIL
    except KeyboardInterrupt:
        print("已取消。", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
