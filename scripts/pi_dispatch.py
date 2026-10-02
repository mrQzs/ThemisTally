#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pi_dispatch —— 规划端（Claude Code 或 Codex）规划 / Pi 执行协作的调度、取证与验收辅助工具。

单文件，仅依赖 Python 3.8+ 标准库，可在 Linux、macOS 与 Windows 上运行。

子命令（对应 方案.md 章节）：
  doctor    环境核验，不调用模型（第 4 节）
  smoke     最小连通性试跑，会调用模型并产生少量费用（第 4.1 节）
  validate  校验任务合同 Markdown + JSON（第 6 节）
  derive-json  由 Markdown 合同生成机器合同 JSON，并立即校验
  baseline  派遣前在基线上运行合同检查，确认探针在修复前会失败
  prepare   建立 attempt 目录与独立 worktree，执行 setup（第 9 节）；提示与未集成 attempt 的范围重叠
  run       预检 Pi，在时限内运行，收集证据（第 8、9、11.2 节）
  collect   调度器异常退出后补做证据收集（--recover）
  check     在固定候选上独立运行合同检查（第 11 节）
  verdict   执行机械门禁并记录验收结论（第 11.3、12 节）
  status    列出 attempt 状态
  metrics   汇总试运行指标（第 13 节）
  branch    为通过验收（或用于返工）的候选创建本地分支（第 12.3、15 节）
  mark      标记 INTEGRATED / ABANDONED
  cleanup   移除 attempt 的 worktree，保留证据（第 15.4 节）
  mutate    在干净副本上逐个套用最小变异，检查测试能否抓住
  wait      等待运行中的 attempt 结束（给没有完成通知的规划端轮询）
  sync-adapters  把 .agents/skills 中的技能复制到 .claude/skills（Claude Code 适配）

它不是安全沙箱：Pi、setup 与检查命令都以调用者的操作系统账户运行。
无人值守或不可信输入必须放进容器、虚拟机或受控沙箱（第 5.4 节）。
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

TOOL_VERSION = "2.2.2"
CONTRACT_SCHEMA_VERSION = 1
MIN_PI_VERSION = (0, 80, 4)  # agent_settled 事件自 0.80.4 起提供
IS_WINDOWS = os.name == "nt"

EXIT_OK, EXIT_FAIL, EXIT_USAGE, EXIT_BLOCKED, EXIT_DRIFT = 0, 1, 2, 3, 4

PLAN_KEY_RE = re.compile(r"^(?P<task>[a-z0-9][a-z0-9-]{0,63})\.v(?P<ver>[1-9][0-9]{0,3})$")
TASK_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
SHA_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
ITEM_ID_RE = re.compile(r"^[A-Z][A-Z0-9_-]{0,31}$")
MODEL_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,199}$")
ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
PLACEHOLDER_RE = re.compile(r"【待填|REPLACE_WITH")
ATTEMPT_DIR_RE = re.compile(r"^attempt-(?P<n>\d{3,})$")
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")

KNOWN_TOOLS = ("read", "bash", "powershell", "edit", "write", "grep", "find", "ls")
DEFAULT_TOOLS = ["read", "grep", "find", "ls", "edit", "write", "bash"]
DEFAULT_THINKING = "high"
FALLBACK_THINKING_LEVELS = ("off", "minimal", "low", "medium", "high", "xhigh", "max")
RESOURCE_FLAGS = ["--no-approve", "--no-extensions", "--no-skills", "--no-prompt-templates", "--no-themes"]
REQUIRED_PI_FLAGS = ["--provider", "--model", "--thinking", "--mode", "--no-session", "--tools"] + RESOURCE_FLAGS
EXECUTOR_ACTIONS = ("local_edit", "local_test", "local_commit", "network")
INTEGRATION_ACTIONS = ("local_branch", "commit", "push", "open_pr", "merge", "deploy")
RISK_LEVELS = ("low", "medium", "high")
EVIDENCE_TOKENS = ("scope", "review")
VERDICTS = ("PASS", "ACCEPTED_WITH_EXCEPTION", "REVISE", "BLOCKED", "ESCALATE")
PASSING_VERDICTS = ("PASS", "ACCEPTED_WITH_EXCEPTION")
FAILURE_CLASSES = ("PLAN_ERROR", "EXECUTION_ERROR", "INFRA_FAILURE", "SCOPE_VIOLATION",
                   "REQUIREMENT_BLOCKED", "TIMEOUT", "BUDGET_EXCEEDED", "CANCELLED")
GATES = ("G0", "G1", "G2", "G3", "G4", "G5", "G6")
REVIEWABLE_STATES = ("NEEDS_REVIEW", "TIMEOUT", "CANCELLED", "INFRA_FAILURE") + VERDICTS
TERMINAL_STATES = VERDICTS + ("INTEGRATED", "ABANDONED", "SUPERSEDED", "TIMEOUT", "CANCELLED",
                              "INFRA_FAILURE", "PREPARE_FAILED", "NEEDS_REVIEW")
REQUIRED_MD_SECTIONS = ("Identity", "Goal", "Non-goals", "Repository facts", "Scope", "Behavior contract",
                        "Steps", "Validation commands", "Definition of done", "Stop conditions", "Budget",
                        "Report back", "Forbidden")

# 执行器永远不得修改的路径：合同、证据、代理规则与调度器本身（不区分大小写匹配）。
PROTECTED_PATTERNS = (
    ".agent/**", ".claude/**", ".codex/**", ".pi/**", ".agents/**", ".gitmodules",
    "**/AGENTS.md", "**/AGENTS.override.md", "**/CLAUDE.md", "**/CLAUDE.local.md",
    "scripts/pi_dispatch.py", "scripts/dispatch-pi.sh",
)
DEPENDENCY_PATTERNS = (
    "**/package.json", "**/package-lock.json", "**/npm-shrinkwrap.json", "**/pnpm-lock.yaml",
    "**/pnpm-workspace.yaml", "**/yarn.lock", "**/bun.lock", "**/bun.lockb", "**/.npmrc",
    "**/requirements*.txt", "**/pyproject.toml", "**/poetry.lock", "**/uv.lock", "**/Pipfile",
    "**/Pipfile.lock", "**/setup.py", "**/setup.cfg", "**/go.mod", "**/go.sum", "**/Cargo.toml",
    "**/Cargo.lock", "**/Gemfile", "**/Gemfile.lock", "**/composer.json", "**/composer.lock",
    "**/pom.xml", "**/build.gradle", "**/build.gradle.kts", "**/gradle.lockfile",
    "**/*.csproj", "**/packages.lock.json", "**/Directory.Packages.props",
)
SENSITIVE_PATTERNS = (
    ".github/**", ".gitlab-ci.yml", ".gitignore", "**/.gitattributes", "**/Makefile", "**/Dockerfile*",
    "**/.env*", "**/tsconfig*.json", "**/vitest.config.*", "**/vite.config.*", "**/jest.config.*",
    "**/karma.conf.*", "**/playwright.config.*", "**/cypress.config.*", "**/pytest.ini",
    "**/conftest.py", "**/tox.ini", "**/noxfile.py", "**/.eslintrc*", "**/eslint.config.*",
    "**/.prettierrc*", "**/biome.json", "**/ruff.toml", "**/.coveragerc",
)
# 这些变量与推送、发布或远程写入相关，默认不传给执行器与检查命令（不是安全边界）。
DEFAULT_ENV_REMOVE = (
    "GITHUB_TOKEN", "GH_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN", "GITLAB_TOKEN",
    "GL_TOKEN", "CI_JOB_TOKEN", "BITBUCKET_TOKEN", "NPM_TOKEN", "NODE_AUTH_TOKEN",
    "YARN_NPM_AUTH_TOKEN", "PYPI_TOKEN", "TWINE_USERNAME", "TWINE_PASSWORD", "CARGO_REGISTRY_TOKEN",
    "GEM_HOST_API_KEY", "NUGET_API_KEY", "SSH_AUTH_SOCK", "SSH_AGENT_PID", "VAULT_TOKEN",
    "CLAUDE_CODE_OAUTH_TOKEN",
)
GIT_REDIRECT_VARS = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
                     "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_COMMON_DIR", "GIT_NAMESPACE", "GIT_PREFIX")
#: 可疑命令中的递归或强制删除；只删工作副本内缓存目录的改记备注（见 _cache_dir_cleanup）。
DELETE_LABEL = "递归或强制删除"
SUSPICIOUS_COMMANDS = (
    (r"\bgit\s+(?:push|commit|merge|rebase|reset|clean|stash(?!\s+(?:list|show)\b)|restore|switch"
     r"|tag(?!\s+(?:-l|--list)\b)|checkout\s+--|branch\s+-[dD])\b",
     "git 写操作"),
    (r"\brm\s+-[A-Za-z]*[rRf]|\bRemove-Item\b.*-Recurse", DELETE_LABEL),
    (r"\b(?:curl|wget|Invoke-WebRequest|iwr|Invoke-RestMethod)\b", "网络下载"),
    (r"\b(?:npm|pnpm|yarn|bun)\s+(?:add|install|i|update|upgrade|remove|uninstall|publish)\b"
     r"|\bpip3?\s+install\b|\buv\s+(?:add|pip)\b|\bpoetry\s+add\b|\bcargo\s+(?:add|install|publish)\b"
     r"|\bgo\s+get\b", "依赖变更或发布"),
    (r"\bsudo\b|\bchmod\b|\bchown\b|\bicacls\b", "权限变更"),
    (r"\b(?:ssh|scp|rsync)\b", "远程访问"),
    (r"(?:^|[;&|]\s*)(?:env|printenv)\s*(?:$|[;&|])|\$env:|Get-ChildItem\s+env:", "读取环境变量"),
    (r"\.ssh[/\\]|id_rsa|id_ed25519|\.aws[/\\]credentials|\.npmrc|\.pypirc|auth\.json", "凭据相关路径"),
)
#: 一次 rm 调用：选项之后、命令分隔符之前是删除目标。
_RM_CALL_RE = re.compile(r"""\brm\s+((?:-[A-Za-z-]+\s+)+)([^;&|\n]*)""")


#: 执行器在命令中创建或使用系统临时目录：这些路径在工作目录之外，运行时才生成，范围检查看不到其中的读写。
#: 覆盖 tempfile（含 `from tempfile import …` 之后的直接调用）、mktemp、PowerShell 与 .NET 的临时文件接口、
#: /tmp、/var/tmp、/private/tmp、$TMPDIR / $TEMP / $TMP、%TEMP%、os.environ 中的 TEMP，以及 Windows 的 Temp 目录。
TEMP_PATH_RE = re.compile(
    r"\btempfile\.\w+|\bfrom\s+tempfile\s+import\b"
    r"|\b(?:mkdtemp|mkstemp|TemporaryDirectory|NamedTemporaryFile|SpooledTemporaryFile|gettempdir)\s*\("
    r"|\bmktemp\b|New-TemporaryFile|GetTempPath|GetTempFileName"
    r"|(?<![\w./~-])(?<!<worktree>)(?:/private)?(?:/var)?/tmp\b"
    r"|\$\{?(?:TMPDIR|TEMP|TMP)\b|\$env:(?:TEMP|TMP)\b|%(?:TEMP|TMP)%"
    r"|\b(?:environ(?:\.get)?\s*[\[(]|getenv\s*\()\s*[\"'](?:TMPDIR|TEMP|TMP)[\"']"
    r"|AppData[\\/]+Local[\\/]+Temp\b|Windows[\\/]+Temp\b", re.I)


def _path_forms(paths: Sequence[Path]) -> List[str]:
    """路径在命令里可能出现的写法：原样、正斜杠、Git Bash 的 /c/…，以及解析后的长路径；按长度从长到短。"""
    forms = set()
    for path in paths:
        for text in {str(path), os.path.realpath(str(path))}:
            slash = text.replace("\\", "/").rstrip("/")
            forms.update({text.rstrip("\\/"), slash})
            if re.match(r"^[A-Za-z]:/", slash):
                forms.add("/" + slash[0].lower() + slash[2:])
    return sorted((form for form in forms if len(form) > 3), key=len, reverse=True)


def _escapes(rest: str) -> bool:
    """路径在目录之后的相对部分（例如 `/src/../x`）规范化之后是否跳出这个目录。"""
    depth = 0
    for part in rest.replace("\\", "/").split("/"):
        if part == "..":
            depth -= 1
            if depth < 0:
                return True
        elif part not in ("", "."):
            depth += 1
    return False


def _mask_paths(command: str, forms: Sequence[str]) -> str:
    """把命令中位于这些目录之内的路径换成 <worktree>：默认的 worktree 建在系统临时目录下，执行器 cd 进自己的
    worktree 不能算作使用临时目录。只屏蔽认得准的完整参数，认不准就保留原文，照常参与临时路径的扫描：

    - 左边界：目录前面不能紧接路径字符，所以 `/var/tmp/wt` 里的 `/tmp/wt` 不算；
    - 右边界：目录后面是路径分隔符或参数结束。放在引号里时，整个参数到对应的引号为止（可以有空格），
      引号前后还拼着别的内容（例如 `"/var""/tmp/wt"`、`"…/wt"-other`）或结束的引号是转义的，都不算；
      不在引号里时，参数到空白或命令分隔符为止，中途出现引号（拼接）时也不算；
    - 目录之后的相对部分含有变量或命令替换（`$`、反引号），或用 `..` 跳出这个目录时，都不算。
    大小写规则跟随本机文件系统。
    """
    flags = re.I if os.name == "nt" else 0
    for form in forms:
        pieces, last = [], 0
        for match in re.finditer(r"(?<![\w./\\~-])" + re.escape(form), command, flags):
            start, end = match.start(), match.end()
            quote = command[start - 1] if start > 0 and command[start - 1] in "\"'" else ""
            if quote:
                # 开引号前面还连着同一个参数（例如 "/var""/tmp/wt"）、或结束的引号是转义的，都认不准
                if start >= 2 and not re.match(r"[\s=(;|&]", command[start - 2]):
                    continue
                close = command.find(quote, end)
                if close < 0 or command[close - 1] == "\\":
                    continue
                rest, after = command[end:close], command[close + 1:close + 2]
            else:
                stop = re.search(r"""[\s;|&)"'`]""", command[end:])
                close = end + stop.start() if stop else len(command)
                rest, after = command[end:close], command[close:close + 1]
                if rest.endswith("\\"):  # 反斜杠转义了空白：参数还没结束，认不准
                    continue
            if (after and not re.match(r"[\s;|&)]", after)) or (rest and rest[0] not in "\\/") \
                    or "$" in rest or "`" in rest or _escapes(rest):
                continue
            pieces.append(command[last:start] + "<worktree>")
            last = end
        command = "".join(pieces) + command[last:]
    return command


#: 删除后不影响候选的缓存目录名（通常被 Git 忽略，跑测试时自动生成）。
_CACHE_DIR_NAMES = ("__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".hypothesis")
_CACHE_TARGET_RE = re.compile(r"""^(["']?)((?:[A-Za-z0-9_.-]+/)*)(%s)/?\1$"""
                              % "|".join(re.escape(name) for name in _CACHE_DIR_NAMES))


def _cache_dir_cleanup(command: str) -> Optional[str]:
    """命令中的递归或强制删除是否只删工作副本内的缓存目录（``__pycache__`` 等）。

    每个 rm 调用的每个目标都必须是相对路径、最后一段是 :data:`_CACHE_DIR_NAMES` 之一，
    且不含 ``..`` 段、绝对路径、``~`` 或变量；只要有一个目标不符合就返回 None，仍按可疑
    命令处理。满足时返回第一个 rm 调用的原文。PowerShell 命令不做判断。
    """
    if re.search(r"\bRemove-Item\b", command, re.I):
        return None
    calls = list(_RM_CALL_RE.finditer(command))
    if not calls:
        return None
    for call in calls:
        targets = call.group(2).split()
        if not targets:
            return None
        for target in targets:
            match = _CACHE_TARGET_RE.match(target)
            if not match or ".." in match.group(2).split("/"):
                return None
    return calls[0].group(0).strip()


def _match_excerpt(text: str, start: int, end: int, width: int = 160) -> str:
    """命中位置所在的那一行；超过 width 时截取命中附近的一段。"""
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    line = text[line_start:line_end if line_end != -1 else len(text)]
    if len(line) > width:
        low = max(0, min(start - line_start - width // 3, len(line) - width))
        line = ("…" if low else "") + line[low:low + width] + ("…" if low + width < len(line) else "")
    return line.strip()


SKIP_MARKER_RE = re.compile(
    r"\.(?:skip|only|todo)\s*\(|\b(?:xit|xdescribe|xtest)\s*\(|@pytest\.mark\.(?:skip|xfail)"
    r"|@unittest\.skip|\bt\.Skip\(|#\[ignore\]|@Disabled\b|@Ignore\b")
ASSERT_RE = re.compile(r"\b(?:expect|assert\w*|should)\b")
STDERR_WARNING_PATTERNS = (
    ("custom_model_id", r"Using custom model id"),
    ("invalid_thinking", r"Invalid thinking level"),
    ("unknown_option", r"Unknown option"),
    ("extension_error", r"Extension error"),
)
# 执行器在推理或回复中提到“合同有歧义或矛盾”的说法。只用来提示验收端核对执行器是否自行选定了某种解释，
# 不参与门禁判定。前面紧跟否定词（no / not / un- / 没有 / 无 / 不 …）的不算。
AMBIGUITY_RE = re.compile(r"ambigu|contradict|inconsisten|矛盾|歧义|含义不明|前后不一致|说法不一", re.I)
# 否定必须紧挨关键词，中间只允许固定的填充词（any、real、seem、任何、发现……）：“no fix for this inconsistency”
# “不可调和的矛盾”否定的不是矛盾本身，仍然计入；merely、仅等词不在填充词里，所以“not merely / 不仅”这类递进
# 也不算否定。
_NEGATION_FILLER = (r"(?:\s+(?:any|an?|the|real|obvious|apparent|actual|further|other|such|seem|seems|appear|appears"
                    r"|to|be|been|at|all|really|truly|actually|found|detected|see|find|notice|spot|detect|observe"
                    r"|internal|logical|major|significant|material|direct|clear|explicit|evident|remaining|new"
                    r"|unresolved|serious|substantive|meaningful))*\s+$")
AMBIGUITY_NEGATION_RE = re.compile(
    r"(?:\bun|\bnon-?)$"
    r"|(?:\b(?:no|any|without|never)\b|(?:\bnot|n't)\b)" + _NEGATION_FILLER +
    r"|(?:没有|并无|不存在|无|并不|不)(?:任何|什么|明显的?|实质性?的?|内在的?|内部的?|逻辑上?的?|发现|看到|找到)*$", re.I)
# 双重否定其实是肯定：“cannot be implemented without contradictions”“并非没有矛盾”，照常计入。
AMBIGUITY_DOUBLE_NEGATION_RE = re.compile(
    r"(?:\b(?:not|cannot|never|impossible)\b|n't\b)[^.;:!?\n]{0,40}\bwithout\b" + _NEGATION_FILLER +
    r"|(?:\bnot|n't)\s+(?:un|non-?)$" +
    r"|(?:并非|不是|并不是|绝非|不)(?:没有|无)(?:任何|什么|明显的?|实质性?的?|内在的?|内部的?|逻辑上?的?|发现|看到|找到)*$",
    re.I)
# 关键词后面直接跟着独立的否定答案：“inconsistencies: none found.”“Contradictions: none.”“矛盾：无。”，或报告
# 标题“### 合同矛盾”下一行的“无”“未发现。”。答案之后必须是句末标点、文本结尾，或换行后接空行、标题、列表，
# 所以“矛盾：未发现解决办法”“inconsistent: no conflicts in the tests were reported”“ambiguous: None of the steps …”
# “inconsistent: no. 4 requires A”与换行续写的“no\nimplementation can …”都仍然计入。单独的 no 不算答案。
AMBIGUITY_RESOLVED_RE = re.compile(
    r"^[A-Za-z]{0,12}[ \t]*[:：?？]?[ \t]*(?:\n[ \t]*(?:[-*>][ \t]*)?)?"
    r"(?:none(?: found)?|nothing found|found none|无|没有|未发现|没有发现|没有矛盾|无矛盾"
    r"|no (?:conflicts?|contradictions?|inconsistenc(?:y|ies)|ambiguit(?:y|ies)|issues?|problems?)"
    r"(?:[ \t]+(?:found|detected))?)"
    r"(?=[ \t]*(?:(?:[。．；;!！]|\.(?![\w(]))(?![ \t]*\d)|$|\n[ \t]*(?:\n|[#>*-]|$)))", re.I)
# 模型把工具调用写进了正文（例如 Qwen / Hermes 风格的 <tool_call><function=edit>…）：Pi 不会执行它，
# 回合随之结束，于是运行“正常完成”却没有做完、也没有报告。
TEXTUAL_TOOL_CALL_RE = re.compile(r"<tool_call>|</tool_call>|<function=[\w.-]+>|<\|tool_call", re.I)
# 附近（前后 240 个字符内）要提到合同、规范、步骤或要求，才算在说合同本身；否则多半是领域用语（如 newline ambiguity）。
AMBIGUITY_CONTEXT_RE = re.compile(r"contract|plan|spec|requirement|\bDoD\b|\bstep\s*\d|合同|规范|步骤|验收|要求", re.I)


class DispatchError(Exception):
    """带退出码的可预期错误；消息面向使用者。"""

    def __init__(self, message: str, code: int = EXIT_BLOCKED) -> None:
        super().__init__(message)
        self.code = code


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------

def utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def read_text_or(path: Path, default: str = "") -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return default


def read_json_or(path: Path, default: Any) -> Any:
    try:
        return read_json(path)
    except (OSError, ValueError):
        return default


def write_json(path: Path, data: Any, exclusive: bool = False) -> None:
    """exclusive=True 用于原始证据：文件已存在时失败，避免覆盖。"""
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if exclusive:
        with open(path, "x", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        return
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    os.replace(str(tmp), str(path))


def write_text(path: Path, text: str, exclusive: bool = True) -> None:
    with open(path, "x" if exclusive else "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def parse_version(text: str) -> Optional[Tuple[int, int, int]]:
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", text or "")
    return tuple(int(x) for x in match.groups()) if match else None  # type: ignore[return-value]


def norm_case(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def is_within(path: Path, root: Path) -> bool:
    child, parent = norm_case(str(path)), norm_case(str(root))
    return child == parent or child.startswith(parent.rstrip("\\/") + os.sep)


def display_path(path: Path, root: Optional[Path] = None) -> str:
    if root is not None and is_within(path, root):
        return os.path.relpath(str(path), str(root)).replace("\\", "/")
    return str(path)


def run_capture(cmd: Sequence[str], cwd: Optional[Path] = None, env: Optional[Dict[str, str]] = None,
                timeout: int = 60) -> Tuple[int, str, str]:
    """运行短命令并捕获输出；stdin 固定为空，避免等待输入。"""
    try:
        proc = subprocess.run(list(cmd), cwd=str(cwd) if cwd else None, env=env, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    except FileNotFoundError as exc:
        return 127, "", str(exc)
    except subprocess.TimeoutExpired:
        return 124, "", "timeout after %ss" % timeout
    except OSError as exc:
        return 126, "", str(exc)
    return proc.returncode, proc.stdout.decode("utf-8", "replace"), proc.stderr.decode("utf-8", "replace")


# ---------------------------------------------------------------------------
# 子进程环境与进程树监督
# ---------------------------------------------------------------------------

def git_env() -> Dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k.upper() not in GIT_REDIRECT_VARS}
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "never"
    env["GIT_OPTIONAL_LOCKS"] = "0"
    return env


def child_env(config: Dict[str, Any], extra: Optional[Dict[str, str]] = None) -> Tuple[Dict[str, str], List[str]]:
    """执行器与检查命令使用的环境：移除仓库重定向变量与推送/发布类凭据，只记录变量名。"""
    keep = {str(k).upper() for k in config.get("env_keep", [])}
    remove = {k.upper() for k in DEFAULT_ENV_REMOVE} | {str(k).upper() for k in config.get("env_remove", [])}
    env: Dict[str, str] = {}
    removed: List[str] = []
    for name, value in os.environ.items():
        upper = name.upper()
        if upper in GIT_REDIRECT_VARS or (upper in remove and upper not in keep):
            removed.append(name)
            continue
        env[name] = value
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "never"
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")  # 避免 __pycache__ 混入候选或造成漂移
    if extra:
        env.update(extra)
    return env, sorted(removed)


class _Interrupted(Exception):
    pass


class _WinJob:
    """Windows Job Object：超时、取消或调度器退出时终止整个进程树。"""

    def __init__(self) -> None:
        import ctypes
        from ctypes import wintypes

        self._ctypes = ctypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateJobObjectW.restype = wintypes.HANDLE
        k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        k32.SetInformationJobObject.restype = wintypes.BOOL
        k32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        k32.QueryInformationJobObject.restype = wintypes.BOOL
        k32.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                                  wintypes.DWORD, ctypes.c_void_p]
        k32.OpenProcess.restype = wintypes.HANDLE
        k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        k32.AssignProcessToJobObject.restype = wintypes.BOOL
        k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        k32.TerminateJobObject.restype = wintypes.BOOL
        k32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        k32.TerminateProcess.restype = wintypes.BOOL
        k32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        k32.CloseHandle.restype = wintypes.BOOL
        k32.CloseHandle.argtypes = [wintypes.HANDLE]
        ntdll = ctypes.WinDLL("ntdll")
        ntdll.NtResumeProcess.restype = ctypes.c_long
        ntdll.NtResumeProcess.argtypes = [wintypes.HANDLE]
        self._k32 = k32
        self._ntdll = ntdll

        class IoCounters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in (
                "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

        class BasicLimit(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong), ("PerJobUserTimeLimit", ctypes.c_longlong),
                        ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                        ("SchedulingClass", wintypes.DWORD)]

        class ExtendedLimit(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", BasicLimit), ("IoInfo", IoCounters),
                        ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

        class BasicAccounting(ctypes.Structure):
            _fields_ = [("TotalUserTime", ctypes.c_longlong), ("TotalKernelTime", ctypes.c_longlong),
                        ("ThisPeriodTotalUserTime", ctypes.c_longlong),
                        ("ThisPeriodTotalKernelTime", ctypes.c_longlong),
                        ("TotalPageFaultCount", wintypes.DWORD), ("TotalProcesses", wintypes.DWORD),
                        ("ActiveProcesses", wintypes.DWORD), ("TotalTerminatedProcesses", wintypes.DWORD)]

        self._accounting_type = BasicAccounting
        self.handle = k32.CreateJobObjectW(None, None)
        if not self.handle:
            raise OSError(ctypes.get_last_error(), "CreateJobObjectW failed")
        info = ExtendedLimit()
        info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not k32.SetInformationJobObject(self.handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
            error = ctypes.get_last_error()
            k32.CloseHandle(self.handle)
            self.handle = None
            raise OSError(error, "SetInformationJobObject failed")

    def attach_and_resume(self, proc: "subprocess.Popen[bytes]") -> bool:
        """把以挂起方式创建的进程加入 Job，再恢复运行；失败时终止该进程。

        先加入 Job 再恢复，保证进程的任何子进程都在 Job 内创建，没有监督空窗。
        """
        handle = getattr(proc, "_handle", None)
        opened = None
        if handle is None:  # 兼容没有 _handle 的实现
            # PROCESS_TERMINATE | PROCESS_SET_QUOTA | PROCESS_SUSPEND_RESUME
            opened = self._k32.OpenProcess(0x0001 | 0x0100 | 0x0800, False, proc.pid)
            handle = opened
        if not handle:
            return False
        try:
            if self._k32.AssignProcessToJobObject(self.handle, int(handle)) and \
                    self._ntdll.NtResumeProcess(int(handle)) == 0:
                return True
            self._k32.TerminateProcess(int(handle), 1)
            return False
        finally:
            if opened:
                self._k32.CloseHandle(opened)

    def active_processes(self) -> int:
        accounting = self._accounting_type()
        ok = self._k32.QueryInformationJobObject(self.handle, 1, self._ctypes.byref(accounting),
                                                 self._ctypes.sizeof(accounting), None)
        return int(accounting.ActiveProcesses) if ok else -1

    def terminate(self) -> None:
        if self.handle:
            self._k32.TerminateJobObject(self.handle, 1)

    def close(self) -> None:
        if self.handle:
            self._k32.CloseHandle(self.handle)
            self.handle = None


def _linux_parent_death_signal() -> None:
    """Linux：调度器意外退出时，内核向子进程发送 SIGTERM（尽力而为）。"""
    try:
        import ctypes

        ctypes.CDLL(None, use_errno=True).prctl(1, int(signal.SIGTERM), 0, 0, 0)  # PR_SET_PDEATHSIG
    except Exception:  # noqa: BLE001 - 仅为加固，失败不影响主流程
        pass


def _killpg(pgid: int, sig: int) -> bool:
    try:
        os.killpg(pgid, sig)  # type: ignore[attr-defined]
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return False


def _install_interrupt_handlers() -> Dict[int, Any]:
    def handler(signum: int, _frame: Any) -> None:
        raise _Interrupted(signum)

    previous: Dict[int, Any] = {}
    names = ["SIGINT", "SIGTERM", "SIGHUP", "SIGBREAK"]
    for name in names:
        sig = getattr(signal, name, None)
        if sig is None:
            continue
        try:
            previous[sig] = signal.signal(sig, handler)
        except (ValueError, OSError):
            pass
    return previous


def _restore_handlers(previous: Dict[int, Any]) -> None:
    for sig, old in previous.items():
        try:
            signal.signal(sig, old)
        except (ValueError, OSError):
            pass


def _terminate_tree(proc: "subprocess.Popen[bytes]", job: Optional[_WinJob], grace: float) -> None:
    if IS_WINDOWS:
        try:
            proc.send_signal(signal.CTRL_BREAK_EVENT)  # type: ignore[attr-defined]
        except (OSError, ValueError, AttributeError):
            pass
        try:
            proc.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            pass
        if job is not None:
            job.terminate()
        else:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], stdin=subprocess.DEVNULL,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            pass
        return
    # POSIX：先 SIGTERM 给整个进程组（Pi 会清理自己跟踪的脱离子进程），宽限后 SIGKILL。
    _killpg(proc.pid, signal.SIGTERM)
    try:
        proc.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        pass
    _killpg(proc.pid, signal.SIGKILL)
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        pass


def _reap_stragglers(proc: "subprocess.Popen[bytes]", job: Optional[_WinJob]) -> Optional[bool]:
    """主进程结束后，终止仍在运行的同组子进程；返回是否发现残留。"""
    if IS_WINDOWS:
        if job is None:
            return None
        count = job.active_processes()
        if count > 0:
            job.terminate()
            return True
        return False if count == 0 else None
    try:
        os.killpg(proc.pid, 0)  # type: ignore[attr-defined]
    except ProcessLookupError:
        return False
    except PermissionError:
        return None
    _killpg(proc.pid, signal.SIGKILL)
    return True


def run_supervised(cmd: Sequence[str], cwd: Path, env: Dict[str, str], stdout: Any, stderr: Any,
                   timeout: Optional[float], grace: float = 15.0,
                   on_spawn: Optional[Any] = None) -> Dict[str, Any]:
    """在独立进程组 / Job Object 中运行命令，执行墙钟时限，结束后清理残留进程。

    stdin 固定为空设备：Pi 在 stdin 不是终端时会读取到 EOF，继承未关闭的管道会导致挂起。
    """
    result: Dict[str, Any] = {"exit_code": None, "timed_out": False, "interrupted": False,
                              "spawn_error": None, "wall_seconds": 0.0, "stray_processes": None,
                              "kill_method": None, "pid": None}
    kwargs: Dict[str, Any] = {"cwd": str(cwd), "env": env, "stdin": subprocess.DEVNULL,
                              "stdout": stdout, "stderr": stderr}
    job: Optional[_WinJob] = None
    if IS_WINDOWS:
        try:
            job = _WinJob()
        except Exception as exc:  # noqa: BLE001
            result["spawn_error"] = "无法创建 Windows Job Object，拒绝在没有进程树监督的情况下运行：%s" % exc
            return result
        # 挂起创建：加入 Job 之后才恢复，子进程不会逃出监督。
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200) | 0x00000004
        result["kill_method"] = "job-object"
    else:
        kwargs["start_new_session"] = True  # 子进程从创建起就在自己的进程组中
        if sys.platform.startswith("linux"):
            kwargs["preexec_fn"] = _linux_parent_death_signal
        result["kill_method"] = "process-group"
    previous = _install_interrupt_handlers()
    proc: Optional["subprocess.Popen[bytes]"] = None
    start = time.monotonic()
    try:
        try:
            proc = subprocess.Popen(list(cmd), **kwargs)
        except OSError as exc:
            result["spawn_error"] = "%s: %s" % (type(exc).__name__, exc)
            return result
        result["pid"] = proc.pid
        if job is not None and not job.attach_and_resume(proc):
            result["spawn_error"] = "进程未能加入 Job Object，已在启动前终止"
            return result
        if on_spawn is not None:
            on_spawn(proc.pid)
        deadline = None if not timeout else start + float(timeout)
        while True:
            remaining = None if deadline is None else deadline - time.monotonic()
            if remaining is not None and remaining <= 0:
                result["timed_out"] = True
                _terminate_tree(proc, job, grace)
                break
            try:
                proc.wait(timeout=1.0 if remaining is None else max(0.05, min(1.0, remaining)))
                break
            except subprocess.TimeoutExpired:
                continue
    except _Interrupted:
        result["interrupted"] = True
        if proc is not None:
            _terminate_tree(proc, job, grace)
    except BaseException:
        if proc is not None:
            _terminate_tree(proc, job, min(grace, 5.0))
        raise
    finally:
        _restore_handlers(previous)
        if proc is not None:
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                pass
            result["stray_processes"] = _reap_stragglers(proc, job)
            result["exit_code"] = proc.returncode
        result["wall_seconds"] = round(time.monotonic() - start, 3)
        if job is not None:
            job.close()
    return result


def pid_alive(pid: Optional[int]) -> Optional[bool]:
    if not pid:
        return None
    if IS_WINDOWS:
        code, out, _ = run_capture(["tasklist", "/FI", "PID eq %d" % pid, "/NH"], timeout=20)
        if code != 0:
            return None
        return str(pid) in out.split()
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


# ---------------------------------------------------------------------------
# Git
# ---------------------------------------------------------------------------

def git(args: Sequence[str], cwd: Path, *, env: Optional[Dict[str, str]] = None, index_file: Optional[Path] = None,
        check: bool = True) -> "subprocess.CompletedProcess[bytes]":
    run_env = dict(env) if env is not None else git_env()
    if index_file is not None:
        run_env["GIT_INDEX_FILE"] = str(index_file)
    cmd = ["git", "-c", "core.fsmonitor=false", "-c", "core.quotepath=off"] + list(args)
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), env=run_env, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError:
        raise DispatchError("未找到 git，请先安装 Git。")
    if check and proc.returncode != 0:
        message = proc.stderr.decode("utf-8", "replace").strip() or proc.stdout.decode("utf-8", "replace").strip()
        raise DispatchError("git %s 失败：%s" % (" ".join(args[:2]), message))
    return proc


def git_text(args: Sequence[str], cwd: Path, **kwargs: Any) -> str:
    return git(args, cwd, **kwargs).stdout.decode("utf-8", "replace").strip()


def resolve_commit(repo_root: Path, sha: str) -> Optional[str]:
    proc = git(["rev-parse", "--verify", "--quiet", sha + "^{commit}"], repo_root, check=False)
    return proc.stdout.decode().strip() if proc.returncode == 0 else None


def effective_autocrlf(repo_root: Path) -> str:
    """当前对本仓库生效的 core.autocrlf（true / false / input / unset）。"""
    proc = git(["config", "--get", "core.autocrlf"], repo_root, check=False)
    value = proc.stdout.decode("utf-8", "replace").strip().lower() if proc.returncode == 0 else ""
    return value or "unset"


def line_ending_args(autocrlf: Optional[str]) -> List[str]:
    """把 prepare 时记录的 core.autocrlf 固定进 git 命令：证据不该随后来的全局配置变化而漂移。

    2026-09-24 实机：系统级 gitconfig 在运行期间被外部重写（autocrlf 由 true 变 false），autocrlf=true
    检出的 CRLF 工作副本在 verdict 重新快照时不再归一，G6 把所有文本文件都报成“候选被修改”。
    """
    if autocrlf in ("true", "false", "input"):
        return ["-c", "core.autocrlf=%s" % autocrlf]
    if autocrlf == "unset":
        return ["-c", "core.autocrlf=false"]
    return []


def snapshot_tree(work_dir: Path, base: str, scratch_dir: Path, label: str, autocrlf: Optional[str] = None) -> str:
    """用临时索引记录工作副本的完整内容（已跟踪 + 未忽略的新文件），返回树对象 ID。

    不修改工作副本的真实索引与 HEAD，也不创建提交。`autocrlf` 是 prepare 时记录的值，
    传入后行尾归一化不再依赖当前配置。
    """
    index = scratch_dir / (".%s.index" % label)
    for stale in (index, index.with_name(index.name + ".lock")):
        if stale.exists():
            stale.unlink()
    try:
        git(["read-tree", base], work_dir, index_file=index)
        git(line_ending_args(autocrlf) + ["add", "-A", "--", "."], work_dir, index_file=index)
        return git_text(["write-tree"], work_dir, index_file=index)
    finally:
        for stale in (index, index.with_name(index.name + ".lock")):
            if stale.exists():
                try:
                    stale.unlink()
                except OSError:
                    pass


def tree_from_patch(repo_root: Path, base: str, patch: Path, scratch_dir: Path,
                    autocrlf: Optional[str] = None) -> str:
    """在临时索引上把补丁应用到基线，重建候选树（用于往返校验与恢复）。"""
    index = scratch_dir / ".roundtrip.index"
    if index.exists():
        index.unlink()
    try:
        git(["read-tree", base], repo_root, index_file=index)
        if patch.stat().st_size > 0:
            git(line_ending_args(autocrlf) + ["apply", "--cached", "--binary", "--whitespace=nowarn", str(patch)],
                repo_root, index_file=index)
        return git_text(["write-tree"], repo_root, index_file=index)
    finally:
        if index.exists():
            index.unlink()


def diff_raw(cwd: Path, base: str, tree: str) -> List[Dict[str, str]]:
    out = git(["diff", "--raw", "-z", "--no-renames", "--no-abbrev", "--no-ext-diff", "--no-textconv",
               base, tree], cwd).stdout
    parts = out.split(b"\0")
    changes: List[Dict[str, str]] = []
    index = 0
    while index < len(parts) - 1:
        meta = parts[index].decode("ascii", "replace")
        if not meta.startswith(":"):
            index += 1
            continue
        raw_path = parts[index + 1]
        try:
            path, decode_error = raw_path.decode("utf-8"), False
        except UnicodeDecodeError:
            path, decode_error = raw_path.decode("utf-8", "replace"), True
        old_mode, new_mode, _old_sha, _new_sha, status = meta[1:].split(" ")
        item = {"path": path, "status": status[:1], "old_mode": old_mode, "new_mode": new_mode}
        if decode_error:
            item["path_decode_error"] = "true"
        changes.append(item)
        index += 2
    return changes


def line_endings_only(cwd: Path, tree_a: str, tree_b: str) -> bool:
    """两棵树的差异是否只是行尾（CRLF / LF）。用于把“配置变了”与“候选被改了”分开。"""
    proc = git(["diff", "--quiet", "--ignore-cr-at-eol", tree_a, tree_b, "--"], cwd, check=False)
    return proc.returncode == 0


def tree_drift(cwd: Path, candidate_tree: str, current_tree: str) -> Dict[str, List[str]]:
    """比较候选树与当前树：修改/删除候选文件是漂移；只新增文件视为检查或复审产生的额外产物。"""
    if candidate_tree == current_tree:
        return {"modified": [], "added": []}
    changes = diff_raw(cwd, candidate_tree, current_tree)
    return {"modified": [c["path"] for c in changes if c["status"] != "A"],
            "added": [c["path"] for c in changes if c["status"] == "A"]}


def ignored_inventory(work_dir: Path) -> List[str]:
    out = git(["ls-files", "--others", "--ignored", "--exclude-standard", "--directory", "-z"], work_dir,
              check=False).stdout
    return sorted({item.decode("utf-8", "replace") for item in out.split(b"\0") if item})


def main_repo_fingerprint(repo_root: Path, scratch_dir: Path) -> Dict[str, Any]:
    """主工作区指纹：HEAD + 工作区内容树（已跟踪文件与未被忽略的新文件的内容）。

    用内容而不是 `git status` 的状态字节：已经是脏文件、运行中又被改写的情况也能发现。
    覆盖范围不含被 .gitignore 忽略的文件与仓库之外的路径。
    """
    head = git(["rev-parse", "--verify", "--quiet", "HEAD"], repo_root, check=False).stdout.decode().strip()
    index = scratch_dir / ".main-fingerprint.index"
    for stale in (index, index.with_name(index.name + ".lock")):
        if stale.exists():
            stale.unlink()
    try:
        if head:
            git(["read-tree", head], repo_root, index_file=index)
        git(["add", "-A", "--", "."], repo_root, index_file=index)
        tree = git_text(["write-tree"], repo_root, index_file=index)
    except DispatchError as exc:
        tree = "error: %s" % exc
    finally:
        for stale in (index, index.with_name(index.name + ".lock")):
            if stale.exists():
                try:
                    stale.unlink()
                except OSError:
                    pass
    return {"head": head, "content_tree": tree}


def main_repo_changes(repo_root: Path, before: Dict[str, Any], after: Dict[str, Any],
                      planner: Sequence[str]) -> Dict[str, Any]:
    """比较运行前后的主工作区指纹，列出变化的路径，并把规划器自己的路径与其他路径分开。

    只在两次指纹都有效时比较内容树；HEAD 变化单独报告（并行批次提前集成、越界提交都会导致）。
    """
    result: Dict[str, Any] = {
        "changed": bool(before) and before != after,
        "head_before": before.get("head"), "head_after": after.get("head"),
        "head_changed": bool(before) and before.get("head") != after.get("head"),
        "planner_paths": [], "other_paths": [], "diff_error": None,
    }
    tree_before, tree_after = before.get("content_tree") or "", after.get("content_tree") or ""
    if not result["changed"] or tree_before == tree_after:
        return result
    if not SHA_RE.match(tree_before) or not SHA_RE.match(tree_after):
        result["diff_error"] = "指纹不完整，无法列出变化的路径"
        return result
    proc = git(["diff-tree", "-r", "--no-renames", "--name-status", "-z", tree_before, tree_after],
               repo_root, check=False)
    if proc.returncode != 0:
        result["diff_error"] = proc.stderr.decode("utf-8", "replace").strip()[:300] or "git diff-tree 失败"
        return result
    fields = proc.stdout.decode("utf-8", "replace").split("\0")
    compiled = compile_patterns(planner, ignore_case=IS_WINDOWS)
    for index in range(0, len(fields) - 1, 2):
        status, path = fields[index], fields[index + 1]
        if not status or not path:
            continue
        entry = "%s %s" % (status, path)
        (result["planner_paths"] if matches(compiled, path) else result["other_paths"]).append(entry)
    result["planner_paths"] = result["planner_paths"][:200]
    result["other_paths"] = result["other_paths"][:200]
    return result


# ---------------------------------------------------------------------------
# 仓库、配置与路径模式
# ---------------------------------------------------------------------------

class Repo:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.agent_dir = root / ".agent"
        self.plans_dir = self.agent_dir / "plans"
        self.runs_dir = self.agent_dir / "runs"
        self.reviews_dir = self.agent_dir / "reviews"

    @classmethod
    def discover(cls, start: Optional[str]) -> "Repo":
        base = Path(start or os.getcwd()).resolve()
        proc = git(["rev-parse", "--show-toplevel", "--git-dir", "--git-common-dir"], base, check=False)
        if proc.returncode != 0:
            raise DispatchError("当前目录不在 Git 仓库中：%s" % base, EXIT_USAGE)
        top, git_dir, common = proc.stdout.decode("utf-8", "replace").splitlines()[:3]
        if norm_case(str((base / git_dir).resolve())) != norm_case(str((base / common).resolve())):
            raise DispatchError("请在主工作区运行本工具，而不是在 worktree 中：%s" % top, EXIT_USAGE)
        return cls(Path(top).resolve())

    def plan_paths(self, key: str) -> Tuple[Path, Path]:
        return self.plans_dir / (key + ".md"), self.plans_dir / (key + ".json")

    def config(self) -> Dict[str, Any]:
        path = self.agent_dir / "dispatch.config.json"
        if not path.exists():
            return {}
        try:
            data = read_json(path)
        except ValueError as exc:
            raise DispatchError("无法解析 %s：%s" % (path, exc), EXIT_USAGE)
        if not isinstance(data, dict):
            raise DispatchError("%s 顶层必须是对象" % path, EXIT_USAGE)
        return data

    def worktree_root(self, config: Dict[str, Any]) -> Path:
        configured = config.get("worktree_root") or os.environ.get("PI_DISPATCH_WORKTREE_ROOT")
        root = Path(os.path.expanduser(str(configured))) if configured else Path(tempfile.gettempdir()) / "pi-worktrees"
        root = root.resolve()
        if is_within(root, self.root):
            raise DispatchError("worktree_root 不能位于仓库内部：%s" % root, EXIT_USAGE)
        return root


def extra_protected_paths(config: Dict[str, Any]) -> List[str]:
    """仓库级受保护路径（例如规范文档、编排记录），与内置的受保护路径一样对执行器永远只读。"""
    values = config.get("extra_protected_paths", [])
    if not isinstance(values, list) or not all(isinstance(v, str) and not pattern_error(v) for v in values):
        raise DispatchError("dispatch.config.json 的 extra_protected_paths 必须是仓库相对路径模式的数组", EXIT_USAGE)
    return list(values)


#: 规划器在派遣期间会写的主工作区路径（合同、复审记录、路线图等）。运行期间这些路径的变化
#: 只作备注，不列入“复审需要关注”；其余路径的变化仍然提示复审确认。
DEFAULT_PLANNER_PATHS = (".agent/plans/**", ".agent/reviews/**", ".agent/design/**", ".agent/*.md")


def planner_paths(config: Dict[str, Any]) -> List[str]:
    """规划器自己会编辑的主工作区路径模式（dispatch.config.json 的 planner_paths，缺省见上）。"""
    values = config.get("planner_paths", list(DEFAULT_PLANNER_PATHS))
    if not isinstance(values, list) or not all(isinstance(v, str) and not pattern_error(v) for v in values):
        raise DispatchError("dispatch.config.json 的 planner_paths 必须是仓库相对路径模式的数组", EXIT_USAGE)
    return list(values)


def plan_key_from_arg(repo: "Repo", value: str) -> str:
    """接受计划标识（task-id.vN），也接受 .agent/plans/ 下合同文件的路径（.md 或 .json）。"""
    text = str(value).strip()
    if PLAN_KEY_RE.match(text):
        return text
    path = Path(text)
    stem = path.name
    for suffix in (".md", ".json"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    if stem != path.name and PLAN_KEY_RE.match(stem):
        resolved = (path if path.is_absolute() else Path.cwd() / path).resolve()
        if norm_case(str(resolved.parent)) == norm_case(str(repo.plans_dir.resolve())):
            return stem
        raise DispatchError("合同文件必须位于 %s 下：%s" % (display_path(repo.plans_dir, repo.root), text), EXIT_USAGE)
    raise DispatchError("计划标识不合法：%s（格式 task-id.vN，例如 normalize-query.v1；"
                        "也可以写成 .agent/plans/<task-id>.vN.md）" % text, EXIT_USAGE)


def git_identity_problem(repo_root: Path) -> Optional[str]:
    """branch 用 git commit-tree 创建候选提交，需要作者与提交者身份。缺失时返回说明，否则 None。

    与 commit-tree 同一套判定：git var 同样读取 user.name / user.email 与 GIT_AUTHOR_* / GIT_COMMITTER_* 环境变量。
    """
    for var in ("GIT_AUTHOR_IDENT", "GIT_COMMITTER_IDENT"):
        if git(["var", var], repo_root, check=False).returncode != 0:
            return ("没有可用的 Git 作者身份（%s）：branch 生成候选提交时会失败。配置 user.name 与 user.email，"
                    "或在运行 branch 时提供 GIT_AUTHOR_NAME / GIT_AUTHOR_EMAIL / GIT_COMMITTER_NAME / "
                    "GIT_COMMITTER_EMAIL 环境变量" % var)
    return None


#: 提交尾注的格式：单行 `Key: value`。控制字符另由 valid_trailer 拒绝。
TRAILER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9-]*: \S.*$")


def valid_trailer(value: Any) -> bool:
    """单行 `Key: value`：值不能为空，也不能含回车、换行、制表符等控制字符（回车会重新带出 CRLF）。"""
    return isinstance(value, str) and bool(TRAILER_RE.match(value)) \
        and not any(ord(ch) < 32 or ord(ch) == 127 for ch in value)


def commit_trailers(config: Dict[str, Any]) -> List[str]:
    """branch 创建候选提交时追加的尾注，例如署名行；每条必须是单行的 `Key: value`。"""
    values = config.get("commit_trailers", [])
    if not isinstance(values, list) or not all(valid_trailer(v) for v in values):
        raise DispatchError("dispatch.config.json 的 commit_trailers 必须是单行 `Key: value` 字符串数组，"
                            "不能含回车、换行等控制字符", EXIT_USAGE)
    return list(values)


def glob_regex(pattern: str, ignore_case: bool = False) -> "re.Pattern[str]":
    """仓库相对 POSIX 路径模式：* 匹配单层，** 匹配任意层级，? 匹配单个字符。"""
    out: List[str] = []
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if pattern.startswith("**/", index):
            out.append("(?:[^/]+/)*")
            index += 3
        elif pattern.startswith("**", index):
            out.append(".*")
            index += 2
        elif char == "*":
            out.append("[^/]*")
            index += 1
        elif char == "?":
            out.append("[^/]")
            index += 1
        else:
            out.append(re.escape(char))
            index += 1
    return re.compile("".join(out), re.IGNORECASE if ignore_case else 0)


def compile_patterns(patterns: Sequence[str], ignore_case: bool = False) -> List["re.Pattern[str]"]:
    return [glob_regex(p, ignore_case) for p in patterns]


def matches(compiled: Sequence["re.Pattern[str]"], path: str) -> bool:
    # fullmatch：`$` 会匹配末尾换行之前的位置，不能用 match + 锚点。
    return any(regex.fullmatch(path) for regex in compiled)


def has_control_chars(text: str) -> bool:
    return any(ord(ch) < 32 or ord(ch) == 127 for ch in text)


def pattern_error(pattern: Any) -> Optional[str]:
    if not isinstance(pattern, str) or not pattern:
        return "必须是非空字符串"
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in pattern):
        return "包含控制字符"
    if "\\" in pattern:
        return "请使用正斜杠"
    if pattern.startswith("/") or re.match(r"^[A-Za-z]:", pattern) or pattern.startswith("~"):
        return "不能是绝对路径"
    if any(part in ("", ".", "..") for part in pattern.split("/")):
        return "不能包含空段、'.' 或 '..'"
    if pattern in ("*", "**", "**/*"):
        return "范围过宽"
    return None


# ---------------------------------------------------------------------------
# 合同校验
# ---------------------------------------------------------------------------

def _md_section(md: str, name: str) -> Optional[str]:
    match = re.search(r"^##\s+%s\s*$(.*?)(?=^##\s|\Z)" % re.escape(name), md, re.M | re.S | re.I)
    return match.group(1) if match else None


#: 单值字段结尾的括号说明，例如 `forbidden（只加命令入口）`、`medium (改动集中)`。
_VALUE_NOTE_RE = re.compile(r"\s*(?:（[^（）]*）|\([^()]*\))\s*$")


def _md_value(raw: str) -> str:
    """Markdown 单值字段的取值：去掉反引号与结尾的括号说明（与列表字段的“无（…）”一致）。"""
    return _VALUE_NOTE_RE.sub("", raw.strip("` ")).strip("` ")


def _md_identity(md: str) -> Dict[str, str]:
    section = _md_section(md, "Identity") or ""
    identity: Dict[str, str] = {}
    for line in section.splitlines():
        match = re.match(r"^\s*[-*]\s*([A-Za-z_]+)\s*:\s*(.+?)\s*$", line)
        if match:
            identity[match.group(1)] = _md_value(match.group(2))
    return identity


def _validate_command(item: Any, group: str, seen: Dict[str, str], errors: List[str]) -> None:
    where = "%s 项" % group
    if not isinstance(item, dict):
        errors.append("%s 必须是对象" % where)
        return
    cid = item.get("id")
    if not isinstance(cid, str) or not ITEM_ID_RE.match(cid):
        errors.append("%s 的 id 不合法：%r（例如 V01、S01）" % (where, cid))
        cid = str(cid)
    elif cid in seen:
        errors.append("id 重复：%s" % cid)
    seen[cid] = group
    argv = item.get("argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(a, str) and a for a in argv):
        errors.append("%s argv 必须是非空字符串数组" % cid)
    elif any("\0" in a for a in argv):
        errors.append("%s argv 含 NUL 字符" % cid)
    cwd = item.get("cwd", ".")
    if cwd != "." and pattern_error(cwd):
        errors.append("%s cwd 不合法：%s" % (cid, pattern_error(cwd)))
    timeout = item.get("timeout_seconds")
    if not isinstance(timeout, int) or isinstance(timeout, bool) or not 1 <= timeout <= 86400:
        errors.append("%s timeout_seconds 必须是 1..86400 的整数" % cid)
    if not isinstance(item.get("expected_exit_code", 0), int):
        errors.append("%s expected_exit_code 必须是整数" % cid)
    if group == "checks" and not isinstance(item.get("required", True), bool):
        errors.append("%s required 必须是布尔值" % cid)
    if group == "checks" and item.get("expect_on_base", "any") not in ("any", "fail", "pass"):
        errors.append("%s expect_on_base 只能是 fail、pass 或 any" % cid)
    for key in ("output_must_match", "output_must_not_match"):
        patterns = item.get(key, [])
        if not isinstance(patterns, list) or not all(isinstance(p, str) for p in patterns):
            errors.append("%s %s 必须是字符串数组" % (cid, key))
            continue
        for pattern in patterns:
            try:
                re.compile(pattern)
            except re.error as exc:
                errors.append("%s %s 正则无效：%s" % (cid, key, exc))
    env = item.get("env", {})
    if not isinstance(env, dict) or not all(isinstance(k, str) and ENV_NAME_RE.match(k) and isinstance(v, str)
                                            for k, v in env.items()):
        errors.append("%s env 必须是 {变量名: 字符串}" % cid)


def normalize_contract(raw: Dict[str, Any]) -> Dict[str, Any]:
    """补齐可选字段的默认值，返回新字典；类型错误的字段原样保留，交给校验报告。"""
    contract = json.loads(json.dumps(raw))
    defaults = {
        "executor": {"thinking": DEFAULT_THINKING, "tools": list(DEFAULT_TOOLS), "context_files": "project"},
        "scope": {"allowed_modified_files": [], "allowed_new_files": [], "allowed_deleted_files": [],
                  "forbidden_paths": [], "dependency_changes": "forbidden"},
        "authorization": {"executor": ["local_edit", "local_test"], "integration": []},
        "budget": {"max_attempts_total": 2, "max_wall_seconds_per_attempt": 1200,
                   "max_wall_seconds_total": 2400, "cost_budget": None},
    }
    for section, values in defaults.items():
        target = contract.setdefault(section, {})
        if isinstance(target, dict):
            for key, value in values.items():
                target.setdefault(key, value)
    for section in ("setup", "checks", "definition_of_done"):
        contract.setdefault(section, [])
    for section, values in (("checks", {"cwd": ".", "required": True, "expected_exit_code": 0}),
                            ("setup", {"cwd": ".", "expected_exit_code": 0})):
        if isinstance(contract[section], list):
            for item in contract[section]:
                if isinstance(item, dict):
                    for key, value in values.items():
                        item.setdefault(key, value)
    return contract


def require_authorized_action(contract: Dict[str, Any], action: str, *, integration: bool = False) -> None:
    """在产生副作用的入口再次核对合同授权。

    合同在 prepare 时已经过静态校验，但 attempt 目录中的合同是运行时输入，
    因此 branch 等入口不能只依赖 prepare 的结论。这里不把某个相近动作当作
    替代授权：例如创建候选分支必须明确拥有 integration.local_branch。
    """
    section = "integration" if integration else "executor"
    authorization = contract.get("authorization") if isinstance(contract, dict) else None
    actions = authorization.get(section) if isinstance(authorization, dict) else None
    if not isinstance(actions, list) or not all(isinstance(item, str) for item in actions):
        raise DispatchError("合同授权无效：authorization.%s 必须是字符串数组" % section, EXIT_BLOCKED)
    if action not in actions:
        raise DispatchError("合同未授权动作：authorization.%s 缺少 %s" % (section, action), EXIT_BLOCKED)


def _is_str_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _md_budget(md: str) -> Dict[str, str]:
    section = _md_section(md, "Budget") or ""
    found: Dict[str, str] = {}
    for key in ("max_attempts_total", "max_wall_seconds_per_attempt", "max_wall_seconds_total"):
        match = re.search(r"^\s*[-*]\s*%s\s*:\s*`?(\d+)" % key, section, re.M)
        if match:
            found[key] = match.group(1)
    return found


def _md_scope_lists(md: str) -> Dict[str, Any]:
    """解析 Scope：`- key: a, b`（同行）或 `- key:` 后跟缩进的 `  - path` 列表；`无` 表示空。"""
    section = _md_section(md, "Scope") or ""
    lines = section.splitlines()
    found: Dict[str, Any] = {}
    for index, line in enumerate(lines):
        match = re.match(r"^[-*]\s*([a-z_]+)\s*:\s*(.*?)\s*$", line)
        if not match:
            continue
        key, rest = match.group(1), match.group(2)
        if key == "dependency_changes":
            found[key] = _md_value(rest)
            continue
        items: List[str] = []
        if rest and not rest.startswith("无") and rest.lower() not in ("none", "[]"):
            items = [v.strip("` ") for v in re.split(r"[,，、]\s*", rest) if v.strip("` ")]
        else:
            for follow in lines[index + 1:]:
                item = re.match(r"^\s+[-*]\s*(.+?)\s*$", follow)
                if not item:
                    break
                items.append(item.group(1).strip("` "))
        found[key] = items
    return found


_CHECK_LINE_RE = re.compile(
    r"^[-*]\s*(?P<id>[A-Z]\d{2,})(?:（(?P<kind>[^）]*)）|\((?P<kind2>[^)]*)\))?\s*[:：]\s*`(?P<cmd>.+?)`(?P<rest>.*)$")


def _md_command_items(md: str, section_name: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """解析 Validation commands（或 Setup）中的命令行，格式见 contract-template.md。"""
    items: List[Dict[str, Any]] = []
    problems: List[str] = []
    for line in (_md_section(md, section_name) or "").splitlines():
        match = _CHECK_LINE_RE.match(line.strip())
        if not match:
            continue
        cid, cmd, rest = match.group("id"), match.group("cmd"), match.group("rest")
        kind = match.group("kind") or match.group("kind2") or ""
        if cmd.startswith('python -c "') and cmd.endswith('"'):
            argv = ["python", "-c", cmd[len('python -c "'):-1]]
        else:
            import shlex

            try:
                argv = shlex.split(cmd, posix=True)
            except ValueError as exc:
                problems.append("%s 的命令无法拆分：%s" % (cid, exc))
                continue
            if not all(token in line for token in argv):
                problems.append("%s 的命令含引号或转义，无法可靠地还原参数；请手写 JSON 中的 argv" % cid)
                continue
        item: Dict[str, Any] = {"id": cid, "argv": argv, "cwd": "."}
        cwd = re.search(r"cwd\s*[:：]\s*`?([^·`]+?)`?\s*(?:·|$)", rest)
        if cwd and cwd.group(1).strip() not in ("仓库根", ".", "repo root"):
            item["cwd"] = cwd.group(1).strip()
        timeout = re.search(r"超时\s*[:：]\s*(\d+)\s*s", rest) or re.search(r"timeout\s*[:：]\s*(\d+)", rest, re.I)
        item["timeout_seconds"] = int(timeout.group(1)) if timeout else 600
        if section_name == "Validation commands":
            item["required"] = not ("可选" in kind or "optional" in kind.lower())
        code = re.search(r"期望退出码\s*[:：]\s*(-?\d+)", rest)
        item["expected_exit_code"] = int(code.group(1)) if code else 0
        must_part = re.search(r"输出须匹配\s*[:：]?\s*(.*?)(?:[，,]\s*不得|$)", rest)
        if must_part:
            item["output_must_match"] = re.findall(r"`([^`]+)`", must_part.group(1))
        must_not = re.search(r"不得(?:出现|匹配)\s*[:：]?\s*(.*)$", rest)
        if must_not:
            item["output_must_not_match"] = re.findall(r"`([^`]+)`", must_not.group(1))
        markers = kind + rest
        if section_name == "Validation commands" and "基线应失败" in markers:
            item["expect_on_base"] = "fail"
        elif section_name == "Validation commands" and "基线应通过" in markers:
            item["expect_on_base"] = "pass"
        items.append(item)
    return items, problems


#: derive-json 没有 --title、从 Goal 第一行取到的标题超过这个字数时提示改用 --title。
LONG_TITLE_CHARS = 60


def branch_subject(task_id: str, title: Any, plan_version: Any, attempt_no: Any) -> str:
    """分支提交的主题行：``<task-id>: <标题>``。

    标题本身已经以 task-id 加冒号（半角或全角）或空格开头时原样使用，不再重复前缀；
    没有标题时写 ``<task-id>: Pi 候选 vN attempt NNN``。
    """
    if isinstance(title, str) and title.strip():
        text = " ".join(title.split())  # 主题行只能是一行：标题中的换行、回车与连续空白合并成一个空格
        if text.startswith(task_id) and text[len(task_id):len(task_id) + 1] in (":", "：", " "):
            return text
        return "%s: %s" % (task_id, text)
    return "%s: Pi 候选 v%s attempt %03d" % (task_id, plan_version, attempt_no)


def derive_contract_json(md: str, title: Optional[str] = None) -> Tuple[Dict[str, Any], List[str]]:
    """由 Markdown 合同生成机器合同（JSON）。返回（合同, 需要人工处理的问题）。

    只转写 Markdown 中已经写明的内容；生成后仍要经过 validate 的逐项比对。
    """
    problems: List[str] = []
    identity = _md_identity(md)
    first = md.splitlines()[0] if md else ""
    task_match = re.match(r"^#\s*TASK:\s*([a-z0-9][a-z0-9-]*)\s*$", first)
    if not task_match:
        problems.append("第一行必须是 `# TASK: <task-id>`")
    executor = identity.get("executor", "")
    exec_match = re.match(r"^([^/\s]+)/(\S+)\s*·\s*thinking\s+(\S+)", executor)
    if not exec_match:
        problems.append("Identity 的 executor 应写成 `provider/model · thinking <级别>`")
    goal = (_md_section(md, "Goal") or "").strip().splitlines()
    derived_title = title or next((g.strip("-* ").strip() for g in goal if g.strip()), "")
    if not derived_title:
        problems.append("没有标题：请用 --title 指定，或在 Goal 第一行写一句话概括")
    checks, check_problems = _md_command_items(md, "Validation commands")
    setup, setup_problems = _md_command_items(md, "Setup")
    problems += check_problems + setup_problems
    dod: List[Dict[str, Any]] = []
    for line in (_md_section(md, "Definition of done") or "").splitlines():
        match = re.match(r"^\s*[-*]\s*(D\d{2,})\s*[:：]\s*(.+?)\s*$", line)
        if not match:
            continue
        text, _sep, evidence_text = match.group(2).partition("证据")
        evidence = []
        for ref in re.findall(r"(?<![A-Za-z0-9])([A-Z]\d{2,}|scope|review)(?![A-Za-z0-9])", evidence_text):
            if ref not in evidence:
                evidence.append(ref)
        dod.append({"id": match.group(1), "text": text.rstrip("；;，, "), "evidence": evidence})
    scope = _md_scope_lists(md)
    budget = _md_budget(md)
    for key in ("max_attempts_total", "max_wall_seconds_per_attempt", "max_wall_seconds_total"):
        if key not in budget:
            problems.append("Budget 缺少 %s" % key)
    plan_version = identity.get("plan_version", "")
    contract: Dict[str, Any] = {
        "schema_version": 1,
        "task_id": task_match.group(1) if task_match else None,
        "plan_version": int(plan_version) if plan_version.isdigit() else None,
        "title": derived_title[:120],
        "repository": identity.get("repository"),
        "base_sha": identity.get("base_sha"),
        "risk_level": identity.get("risk_level"),
        "authorization": {
            "executor": _md_action_list(identity.get("authorized_actions")),
            "integration": _md_action_list(identity.get("integration_actions")),
        },
        "executor": {
            "provider": exec_match.group(1) if exec_match else None,
            "model": exec_match.group(2) if exec_match else None,
            "thinking": exec_match.group(3) if exec_match else DEFAULT_THINKING,
            "tools": list(DEFAULT_TOOLS), "context_files": "project",
        },
        "scope": {
            "allowed_modified_files": scope.get("allowed_modified_files", []),
            "allowed_new_files": scope.get("allowed_new_files", []),
            "allowed_deleted_files": scope.get("allowed_deleted_files", []),
            "forbidden_paths": scope.get("forbidden_paths", []),
            "dependency_changes": scope.get("dependency_changes", "forbidden"),
        },
        "setup": setup,
        "checks": checks,
        "definition_of_done": dod,
        "budget": {key: int(budget[key]) for key in budget},
    }
    contract["budget"]["cost_budget"] = None
    return contract, problems


def _md_action_list(value: Optional[str]) -> List[str]:
    """与 _md_action_set 相同的解析，但保留书写顺序并去重（用于生成 JSON）。"""
    out: List[str] = []
    for token in re.findall(r"[a-z_]+", value or ""):
        if token != "none" and token not in out:
            out.append(token)
    return out


def _md_action_set(value: Optional[str]) -> Optional[set]:
    """解析 Identity 中的动作列表；none / 无 / 空表示空集合。"""
    if value is None:
        return None
    return {token for token in re.findall(r"[a-z_]+", value) if token != "none"}


def _argv_in_line(argv: List[str], line: str) -> bool:
    """argv 的各个参数须按顺序出现在同一行；程序名只比较文件名主干（忽略目录与扩展名）。"""
    program = re.split(r"[\\/]", argv[0])[-1]
    program = re.sub(r"\.(exe|cmd|bat)$", "", program, flags=re.I)
    position = line.lower().find(program.lower())
    if position < 0:
        return False
    position += len(program)
    for token in argv[1:]:
        found = line.find(token, position)
        if found < 0:
            return False
        position = found + len(token)
    return True


def validate_contract(md_text: str, raw: Any, plan_key: str,
                      extra_protected: Sequence[str] = ()) -> Tuple[Optional[Dict[str, Any]], List[str], List[str]]:
    try:
        return _validate_contract(md_text, raw, plan_key, extra_protected)
    except (TypeError, AttributeError, ValueError, KeyError) as exc:  # 结构异常一律按合同错误报告
        return None, ["合同结构无效：%s: %s" % (type(exc).__name__, exc)], []


def _validate_contract(md_text: str, raw: Any, plan_key: str,
                       extra_protected: Sequence[str] = ()) -> Tuple[Optional[Dict[str, Any]], List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []
    key_match = PLAN_KEY_RE.match(plan_key)
    if not key_match:
        return None, ["计划标识不合法：%s（格式 task-id.vN）" % plan_key], warnings
    if not isinstance(raw, dict):
        return None, ["机器合同顶层必须是 JSON 对象"], warnings
    task_id, version = key_match.group("task"), int(key_match.group("ver"))
    contract = normalize_contract(raw)
    for section in ("executor", "scope", "authorization", "budget"):
        if not isinstance(contract.get(section), dict):
            errors.append("%s 必须是对象" % section)
    for section in ("setup", "checks", "definition_of_done"):
        if not isinstance(contract.get(section), list):
            errors.append("%s 必须是数组" % section)
    if errors:
        return None, errors, warnings
    if contract.get("schema_version") != CONTRACT_SCHEMA_VERSION:
        errors.append("schema_version 必须为 %d" % CONTRACT_SCHEMA_VERSION)
    if contract.get("task_id") != task_id:
        errors.append("task_id 应为 %s，实际为 %r" % (task_id, contract.get("task_id")))
    if contract.get("plan_version") != version:
        errors.append("plan_version 应为 %d，实际为 %r" % (version, contract.get("plan_version")))
    base = contract.get("base_sha")
    if not isinstance(base, str) or not SHA_RE.match(base):
        errors.append("base_sha 必须是完整的 40/64 位小写提交 ID")
    if contract.get("risk_level") not in RISK_LEVELS:
        errors.append("risk_level 必须是 %s 之一" % "/".join(RISK_LEVELS))

    authorization = contract["authorization"]
    executor_actions = authorization.get("executor")
    if not _is_str_list(executor_actions) or not set(executor_actions) <= set(EXECUTOR_ACTIONS):
        errors.append("authorization.executor 只能包含：%s" % ", ".join(EXECUTOR_ACTIONS))
        executor_actions = None
    elif "local_edit" not in executor_actions:
        errors.append("authorization.executor 必须包含 local_edit")
    integration = authorization.get("integration")
    if not _is_str_list(integration) or not set(integration) <= set(INTEGRATION_ACTIONS):
        errors.append("authorization.integration 只能包含：%s" % ", ".join(INTEGRATION_ACTIONS))
        integration = None

    executor = contract["executor"]
    for field in ("provider", "model"):
        value = executor.get(field)
        if value is not None and (not isinstance(value, str) or not MODEL_TOKEN_RE.match(value)):
            errors.append("executor.%s 不合法：%r" % (field, value))
    thinking = executor.get("thinking")
    if not isinstance(thinking, str) or thinking not in FALLBACK_THINKING_LEVELS:
        errors.append("executor.thinking 必须是 %s 之一" % ", ".join(FALLBACK_THINKING_LEVELS))
    tools = executor.get("tools")
    if not _is_str_list(tools) or not tools or not set(tools) <= set(KNOWN_TOOLS):
        errors.append("executor.tools 必须是非空字符串数组，且只含：%s" % ", ".join(KNOWN_TOOLS))
    elif executor_actions and "local_test" in executor_actions and not {"bash", "powershell"} & set(tools):
        warnings.append("授权了 local_test 但工具集没有 bash/powershell：执行器无法自检，检查将只由验收端运行")
    if executor.get("context_files") not in ("project", "none"):
        errors.append("executor.context_files 必须是 project 或 none")

    scope = contract["scope"]
    protected = compile_patterns(list(PROTECTED_PATTERNS) + list(extra_protected), ignore_case=True)
    all_allowed: List[str] = []
    forbidden_list: List[str] = []
    for field in ("allowed_modified_files", "allowed_new_files", "allowed_deleted_files", "forbidden_paths"):
        values = scope.get(field)
        if not isinstance(values, list):
            errors.append("scope.%s 必须是数组" % field)
            continue
        for pattern in values:
            problem = pattern_error(pattern)
            if problem:
                errors.append("scope.%s 中的 %r %s" % (field, pattern, problem))
            elif field == "forbidden_paths":
                forbidden_list.append(pattern)
            else:
                all_allowed.append(pattern)
                if matches(protected, pattern):
                    errors.append("scope.%s 包含受保护路径 %s（合同、代理规则与调度器不得委派修改）"
                                  % (field, pattern))
    if not scope.get("allowed_modified_files") and not scope.get("allowed_new_files"):
        errors.append("scope 至少要允许修改或新增一个文件")
    forbidden = compile_patterns(forbidden_list)
    for pattern in all_allowed:
        if "*" not in pattern and matches(forbidden, pattern):
            errors.append("路径 %s 同时出现在允许集合与 forbidden_paths" % pattern)
    if scope.get("dependency_changes") not in ("forbidden", "allowed"):
        errors.append("scope.dependency_changes 必须是 forbidden 或 allowed")

    seen: Dict[str, str] = {}
    for group in ("setup", "checks"):
        for item in contract[group]:
            _validate_command(item, group, seen, errors)
    checks = [c for c in contract["checks"] if isinstance(c, dict) and isinstance(c.get("id"), str)]
    if not any(c.get("required", True) is True for c in checks):
        errors.append("至少需要一个 required 为 true 的检查：没有可独立运行的检查，验收门禁无法通过")
    check_ids = {c["id"] for c in checks}
    dod = contract["definition_of_done"]
    referenced: set = set()
    dod_ids: List[str] = []
    if not dod:
        errors.append("definition_of_done 必须是非空数组")
    for item in dod:
        if not isinstance(item, dict):
            errors.append("definition_of_done 项必须是对象")
            continue
        did = item.get("id")
        if not isinstance(did, str) or not ITEM_ID_RE.match(did) or did in dod_ids or did in check_ids:
            errors.append("DoD id 不合法或重复：%r" % (did,))
            did = str(did)
        dod_ids.append(did)
        if not isinstance(item.get("text"), str) or not item.get("text"):
            errors.append("%s 缺少 text" % did)
        evidence = item.get("evidence")
        if not _is_str_list(evidence) or not evidence:
            errors.append("%s 的 evidence 必须是非空字符串数组（检查 id、scope 或 review）" % did)
            continue
        for ref in evidence:
            if ref in check_ids:
                referenced.add(ref)
            elif ref not in EVIDENCE_TOKENS:
                errors.append("%s 的证据 %r 不是已定义的检查 id，也不是 scope/review" % (did, ref))
    for check in checks:
        if check.get("required", True) and check["id"] not in referenced:
            warnings.append("必要检查 %s 没有被任何 DoD 引用" % check["id"])

    budget = contract["budget"]
    attempts = budget.get("max_attempts_total")
    per_attempt = budget.get("max_wall_seconds_per_attempt")
    total = budget.get("max_wall_seconds_total")
    if not isinstance(attempts, int) or isinstance(attempts, bool) or not 1 <= attempts <= 20:
        errors.append("budget.max_attempts_total 必须是 1..20 的整数")
    if not isinstance(per_attempt, int) or isinstance(per_attempt, bool) or not 60 <= per_attempt <= 86400:
        errors.append("budget.max_wall_seconds_per_attempt 必须是 60..86400 的整数")
        per_attempt = None
    if not isinstance(total, int) or isinstance(total, bool) or (per_attempt is not None and total < per_attempt):
        errors.append("budget.max_wall_seconds_total 必须是整数且不小于单轮上限")
    cost = budget.get("cost_budget")
    if cost is not None and not (isinstance(cost, dict) and isinstance(cost.get("amount"), (int, float))
                                 and not isinstance(cost.get("amount"), bool) and cost.get("amount") >= 0
                                 and isinstance(cost.get("currency"), str)):
        errors.append("budget.cost_budget 必须为 null 或 {amount, currency}")

    # ---- Markdown 与 JSON：Pi 读 Markdown，调度器执行 JSON，与执行相关的内容必须一致 ----
    raw_text = json.dumps(raw, ensure_ascii=False)
    if PLACEHOLDER_RE.search(md_text):
        errors.append("Markdown 合同仍包含占位符（【待填…】或 REPLACE_WITH…）")
    if PLACEHOLDER_RE.search(raw_text):
        errors.append("JSON 合同仍包含占位符（【待填…】或 REPLACE_WITH…）")
    for section in REQUIRED_MD_SECTIONS:
        if _md_section(md_text, section) is None:
            errors.append("Markdown 缺少章节：## %s" % section)
    title = re.search(r"^#\s+TASK:\s*`?([a-z0-9-]+)", md_text, re.M)
    if not title or title.group(1) != task_id:
        errors.append("Markdown 标题应为 '# TASK: %s'" % task_id)
    identity = _md_identity(md_text)
    for field, expected in (("plan_version", str(version)), ("base_sha", base),
                            ("risk_level", contract.get("risk_level"))):
        if identity.get(field) != expected:
            errors.append("Markdown Identity 的 %s（%r）与 JSON（%r）不一致" % (field, identity.get(field), expected))
    for field, expected_list in (("authorized_actions", executor_actions), ("integration_actions", integration)):
        declared = _md_action_set(identity.get(field))
        if declared is None:
            errors.append("Markdown Identity 缺少 %s" % field)
        elif expected_list is not None and declared != set(expected_list):
            errors.append("Markdown Identity 的 %s（%s）与 JSON（%s）不一致"
                          % (field, ", ".join(sorted(declared)) or "none", ", ".join(sorted(expected_list)) or "none"))
    provider, model = executor.get("provider"), executor.get("model")
    declared_executor = identity.get("executor", "")
    if provider and model and "%s/%s" % (provider, model) not in declared_executor:
        errors.append("Markdown Identity 的 executor 应写明 %s/%s" % (provider, model))
    if isinstance(thinking, str) and not re.search(r"thinking\s+%s\b" % re.escape(thinking), declared_executor):
        errors.append("Markdown Identity 的 executor 应写明 thinking %s" % thinking)
    for pattern in all_allowed + forbidden_list:
        if pattern not in md_text:
            errors.append("Markdown 未列出 JSON 中的路径：%s" % pattern)
    dependency_line = re.search(r"dependency_changes\s*:\s*`?([a-z]+)", _md_section(md_text, "Scope") or "")
    if not dependency_line or dependency_line.group(1) != scope.get("dependency_changes"):
        errors.append("Markdown Scope 的 dependency_changes 与 JSON（%s）不一致" % scope.get("dependency_changes"))
    md_budget = _md_budget(md_text)
    for key, value in (("max_attempts_total", attempts), ("max_wall_seconds_per_attempt", per_attempt),
                       ("max_wall_seconds_total", total)):
        if md_budget.get(key) != str(value):
            errors.append("Markdown Budget 的 %s（%s）与 JSON（%s）不一致" % (key, md_budget.get(key), value))
    validation = _md_section(md_text, "Validation commands") or ""
    for check in checks:
        lines = [line for line in validation.splitlines() if re.search(r"\b%s\b" % re.escape(check["id"]), line)]
        argv = check.get("argv")
        if not lines:
            errors.append("Markdown Validation commands 未列出 %s" % check["id"])
        elif _is_str_list(argv) and argv and not any(_argv_in_line(argv, line) for line in lines):
            errors.append("Markdown 中 %s 的命令与 JSON argv 不一致：%s" % (check["id"], " ".join(argv)))
    for item_id in dod_ids:
        if not re.search(r"\b%s\b" % re.escape(item_id), md_text):
            errors.append("Markdown 未出现 JSON 中的编号：%s" % item_id)
    return (contract if not errors else None), errors, warnings


def invisible_char_warnings(text: str, label: str, limit: int = 5) -> List[str]:
    """合同中的不可见格式字符（Unicode 类别 Cf：零宽字符、双向控制符、BOM、软连字符等）。

    常见来源是编辑工具把 `\\u200e` 这类转义序列写成了实际字符：Markdown 与 JSON 看起来一致，
    校验却对不上，执行器读到的也是不可见字符。
    """
    import unicodedata

    found: List[str] = []
    for number, line in enumerate(text.splitlines(), 1):
        chars = sorted({ch for ch in line if unicodedata.category(ch) == "Cf"})
        if chars:
            found.append("%s 第 %d 行含不可见格式字符 %s：如果本意是写转义序列，请改回转义文本（或在探针里用 chr()）"
                         % (label, number, "、".join("U+%04X" % ord(ch) for ch in chars)))
        if len(found) >= limit:
            break
    return found


def validate_plan(repo: Repo, plan_key: str) -> Tuple[Optional[Dict[str, Any]], List[str], List[str]]:
    if not PLAN_KEY_RE.match(plan_key):
        return None, ["计划标识不合法：%s（格式 task-id.vN，例如 normalize-query.v1）" % plan_key], []
    md_path, json_path = repo.plan_paths(plan_key)
    errors: List[str] = []
    for path in (md_path, json_path):
        if not path.exists():
            errors.append("缺少文件：%s" % display_path(path, repo.root))
        elif path.is_symlink():
            errors.append("合同不能是符号链接：%s" % display_path(path, repo.root))
    if errors:
        return None, errors, []
    md_text = md_path.read_text(encoding="utf-8")
    try:
        raw = json.loads(json_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        return None, ["JSON 合同解析失败：%s" % exc], []
    contract, errors, warnings = validate_contract(md_text, raw, plan_key, extra_protected_paths(repo.config()))
    warnings.extend(invisible_char_warnings(md_text, "Markdown"))
    warnings.extend(invisible_char_warnings(json_path.read_text(encoding="utf-8"), "JSON"))
    base = raw.get("base_sha") if isinstance(raw, dict) else None
    if isinstance(base, str) and SHA_RE.match(base):
        if resolve_commit(repo.root, base) != base:
            errors.append("base_sha 在本仓库中不存在或不是提交：%s" % base)
            contract = None
        else:
            if git(["cat-file", "-e", "%s:AGENTS.md" % base], repo.root, check=False).returncode != 0:
                warnings.append("基线提交中没有 AGENTS.md：worktree 基于基线创建，执行器将看不到执行规则")
            head = git_text(["rev-parse", "HEAD"], repo.root)
            if head != base:
                warnings.append(base_behind_head_message(repo, base, head))
            warnings.extend(missing_fact_path_warnings(repo, md_text, raw, base))
    if git(["check-ignore", "-q", ".agent/runs/probe"], repo.root, check=False).returncode != 0:
        warnings.append(".agent/runs/ 尚未被 .gitignore 忽略；prepare 会拒绝运行")
    return contract, errors, warnings


NOTE_PREFIX = "NOTE："

#: Repository facts 里用反引号写的仓库相对文件：至少一个 `/`，以扩展名结尾，不含通配符。
FACT_PATH_RE = re.compile(r"`([A-Za-z0-9_][A-Za-z0-9_./-]*/[A-Za-z0-9_.-]+\.[A-Za-z0-9]{1,8})`")


def missing_fact_path_warnings(repo: "Repo", md_text: str, raw: Any, base: str) -> List[str]:
    """Repository facts 点名「基线已含」的文件若在基线里不存在，提示规划端。

    并行派遣时最容易把同批另一份合同要产出的文件当成基线已含（2026-09-24 实机：netperf-diff 的合同
    引用了同批 netperf-report 才会产出的 report.ts，执行器只能 BLOCKED，一轮 attempt 白跑）。
    allowed_new_files 里的路径是本任务要新建的，不算；含通配符的模式不查。
    """
    section = _md_section(md_text, "Repository facts") or ""
    scope = raw.get("scope") if isinstance(raw, dict) else None
    new_files = set(scope.get("allowed_new_files") or []) if isinstance(scope, dict) else set()
    candidates: List[str] = []
    for match in FACT_PATH_RE.finditer(section):
        path = match.group(1)
        if path in candidates or path in new_files or any(ch in path for ch in "*?{}"):
            continue
        candidates.append(path)
    # 合同常把路径写成相对项目子目录（检查的 cwd，例如 `UITest/`）的形式：除仓库根外，也按每个 cwd 找一遍。
    roots: List[str] = ["."]
    if isinstance(raw, dict):
        for item in list(raw.get("checks") or []) + list(raw.get("setup") or []):
            cwd = item.get("cwd") if isinstance(item, dict) else None
            if isinstance(cwd, str) and cwd.strip("/") not in ("", ".") and cwd.strip("/") not in roots:
                roots.append(cwd.strip("/"))

    def exists_in_base(path: str) -> bool:
        for root in roots:
            full = path if root == "." else "%s/%s" % (root, path)
            if git(["cat-file", "-e", "%s:%s" % (base, full)], repo.root, check=False).returncode == 0:
                return True
        return False

    missing = [p for p in candidates if not exists_in_base(p)]
    if not missing:
        return []
    return ["Repository facts 提到的文件在基线 %s 中不存在：%s——若它由同批的另一份合同产出，"
            "等那份集成后再以新 HEAD 为基线" % (base[:12], "、".join(missing[:8]))]


def base_behind_head_message(repo: "Repo", base: str, head: str) -> str:
    """base_sha 落后于 HEAD 时的提示。

    按「先提交合同再派遣」的流程，HEAD 总会比基线多出合同、复审记录这类规划路径的提交；这种差异
    不影响执行器看到的代码，降为 NOTE。差异碰到其他路径时仍是 WARN：那意味着执行器拿到的是旧代码。
    """
    proc = git(["diff", "--name-only", base, head, "--"], repo.root, check=False)
    if proc.returncode == 0:
        changed = [line.strip() for line in proc.stdout.decode("utf-8", "replace").splitlines() if line.strip()]
        compiled = compile_patterns(planner_paths(repo.config()), ignore_case=IS_WINDOWS)
        if changed and all(matches(compiled, path) for path in changed):
            return ("%sbase_sha 不是当前 HEAD（%s），但差异只在规划路径（%s）：按「先提交合同再派遣」的流程属正常"
                    % (NOTE_PREFIX, head[:12], "、".join(changed[:5]) + ("…" if len(changed) > 5 else "")))
    return "base_sha 不是当前 HEAD（%s）；确认这是有意选择的输入版本" % head[:12]


# ---------------------------------------------------------------------------
# Pi 命令、预检与上下文证据
# ---------------------------------------------------------------------------

BATCH_UNSAFE_CHARS = set('&|<>^%!"\r\n')


def resolve_pi_command() -> List[str]:
    """定位 pi。Windows 上优先绕过 npm 的 .cmd 包装，直接用 node 运行入口脚本。"""
    override = os.environ.get("PI_DISPATCH_PI_CMD")
    if override:
        try:
            value = json.loads(override)
        except ValueError:
            value = [override]
        if not (isinstance(value, list) and value and all(isinstance(x, str) and x for x in value)):
            raise DispatchError("PI_DISPATCH_PI_CMD 必须是 JSON 字符串数组或单个可执行文件路径", EXIT_USAGE)
        return value
    exe = shutil.which("pi")
    if not exe:
        raise DispatchError("PATH 中找不到 pi；请安装 @earendil-works/pi-coding-agent 或设置 PI_DISPATCH_PI_CMD")
    if IS_WINDOWS and exe.lower().endswith((".cmd", ".bat")):
        try:
            shim = Path(exe).read_text(encoding="utf-8", errors="replace")
        except OSError:
            shim = ""
        match = re.search(r'"%dp0%\\([^"]+?\.(?:c|m)?js)"', shim, re.I)
        if match:
            script = Path(exe).parent / match.group(1)
            local_node = Path(exe).parent / "node.exe"
            node = str(local_node) if local_node.is_file() else shutil.which("node")
            if script.is_file() and node:
                return [node, str(script)]
    return [exe]


def ensure_argv_safe(cmd: Sequence[str]) -> None:
    """Windows 批处理包装会经 cmd.exe 解析参数；含特殊字符时拒绝执行。"""
    if IS_WINDOWS and cmd and cmd[0].lower().endswith((".cmd", ".bat")):
        for arg in cmd[1:]:
            if any(ch in BATCH_UNSAFE_CHARS for ch in arg):
                raise DispatchError("参数 %r 含批处理特殊字符，不能安全传给 %s；"
                                    "请改用 PI_DISPATCH_PI_CMD 指向 node 与入口脚本" % (arg, cmd[0]), EXIT_USAGE)


def pi_agent_dir() -> Path:
    configured = os.environ.get("PI_CODING_AGENT_DIR")
    return Path(os.path.expanduser(configured)) if configured else Path.home() / ".pi" / "agent"


CONTEXT_FILE_NAMES = ("AGENTS.override.md", "AGENTS.md", "AGENTS.MD", "CLAUDE.md", "CLAUDE.MD")
PROJECT_TRUST_RESOURCES = (".pi/settings.json", ".pi/extensions", ".pi/skills", ".pi/prompts", ".pi/themes",
                           ".pi/SYSTEM.md", ".pi/APPEND_SYSTEM.md", ".agents/skills")


def _context_file_in(directory: Path) -> Optional[Path]:
    for name in CONTEXT_FILE_NAMES:  # 与 Pi 相同：每个目录只取第一个存在的文件
        candidate = directory / name
        if candidate.is_file():
            return candidate
    return None


def context_evidence(work_dir: Path, context_mode: str) -> Dict[str, Any]:
    """复现 Pi 的上下文文件发现规则，记录执行器将读取的规则文件（路径与哈希）。"""
    agent_dir = pi_agent_dir()
    files: List[Dict[str, Any]] = []
    warnings: List[str] = []
    if context_mode == "project":
        global_file = _context_file_in(agent_dir)
        if global_file:
            files.append({"scope": "global", "path": str(global_file)})
        chain: List[Tuple[Path, Path]] = []
        current = work_dir.resolve()
        while True:
            found = _context_file_in(current)
            if found:
                chain.append((current, found))
            if current.parent == current:
                break
            current = current.parent
        for directory, found in reversed(chain):
            inside = is_within(directory, work_dir)
            files.append({"scope": "worktree" if inside else "ancestor", "path": str(found)})
            if not inside:
                warnings.append("工作副本之外的上下文文件也会被执行器读取：%s" % found)
    for item in files:
        path = Path(item["path"])
        item["sha256"] = sha256_file(path)
        item["bytes"] = path.stat().st_size
    system_files = []
    for name in ("SYSTEM.md", "APPEND_SYSTEM.md"):
        path = agent_dir / name
        if path.is_file():
            system_files.append({"path": str(path), "sha256": sha256_file(path)})
            warnings.append("全局 %s 会改变执行器系统提示词：%s" % (name, path))
    ignored_resources = [name for name in PROJECT_TRUST_RESOURCES if (work_dir / name).exists()]
    settings_keys: List[str] = []
    settings_path = agent_dir / "settings.json"
    if settings_path.is_file():
        data = read_json_or(settings_path, {})
        settings_keys = sorted(data.keys()) if isinstance(data, dict) else []
    return {"context_mode": context_mode, "agent_dir": str(agent_dir), "context_files": files,
            "global_system_files": system_files, "global_settings_keys": settings_keys,
            "project_resources_ignored_by_no_approve": ignored_resources, "warnings": warnings}


def parse_help(help_text: str) -> Dict[str, Any]:
    text = strip_ansi(help_text)
    flags = sorted(set(re.findall(r"(?<![\w-])(--[a-z][a-z0-9-]*)", text)))
    thinking = list(FALLBACK_THINKING_LEVELS)
    match = re.search(r"--thinking\s+<level>\s+[^:\n]*:\s*([a-z, ]+)", text)
    if match:
        thinking = [x.strip() for x in match.group(1).split(",") if x.strip()]
    tools: List[str] = []
    section = re.search(r"Built-in Tool Names:\s*\n(.*?)(?:\n\s*\n|\Z)", text, re.S)
    if section:
        tools = re.findall(r"^\s+([a-z_]+)\s+-", section.group(1), re.M)
    return {"flags": flags, "thinking_levels": thinking, "builtin_tools": tools}


def list_models_rows(output: str) -> List[Tuple[str, str]]:
    """`pi --list-models` 表格中的 (provider, model)。只解析表头之后的行：没有可用或匹配的模型时，
    Pi 输出的是一句说明（No models available. …、No models matching "…"），不是表格。"""
    rows: List[Tuple[str, str]] = []
    in_table = False
    for line in strip_ansi(output).splitlines():
        parts = line.split()
        if not in_table:
            in_table = parts[:2] == ["provider", "model"]
            continue
        if len(parts) >= 2:
            rows.append((parts[0], parts[1]))
    return rows


def list_models_empty_reason(output: str) -> Optional[str]:
    """Pi 没有输出表格时的原因：no_models（没有任何可用模型）或 no_match（有模型，但没有匹配的）。"""
    text = strip_ansi(output)
    if re.search(r"^No models available\b", text, re.M):
        return "no_models"
    if re.search(r"^No models matching\b", text, re.M):
        return "no_match"
    return None


#: 疑似凭据的键名：api key、token、secret、password、credential。
_SECRET_KEY = (r"[\w.-]*(?:api[ _-]?key|apikey|access[ _-]?key|secret[ _-]?key|private[ _-]?key|auth[ _-]?token"
               r"|token|secret|password|passwd|credential|authorization)[\w.-]*")
_SECRET_KEY_RE = re.compile(r"^%s$" % _SECRET_KEY, re.I)
#: Bearer 令牌与常见的令牌前缀（sk-、ghp_ 等）。
_SECRET_TOKEN_RE = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}"
                              r"|\b(?:sk|pk|rk|ghp|gho|ghu|ghs|github_pat|xox[abpr])[-_][A-Za-z0-9_-]{8,}", re.I)
#: PEM 私钥：整块遮蔽，没有结束行时遮到输出结尾。
_SECRET_PEM_RE = re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z0-9 ]*PRIVATE KEY-----|\Z)")
#: 疑似凭据的键（key=value、"key": value，键名可以带任意层转义的引号）：后面的值一直遮到行尾，并连同后面
#: 缩进的续行一起遮蔽。值在本行确定不了结束时（见 _value_ends_on_line），遮蔽这条输出的其余部分。
_SECRET_KV_RE = re.compile(
    r"""((?:\\*["'])?%s(?:\\*["'])?[ \t]*[:=][ \t]*)([^\n]*)(?:\n[ \t]+[^\n]*)*""" % _SECRET_KEY, re.I)


def _value_ends_on_line(value: str) -> bool:
    """敏感值是否在本行完整结束。空值、以 { [ ( 开头、以逗号、反斜杠、{ [ ( 或冒号结尾、YAML 块标量的起始标记
    （| |- > >- |2- |-2 等，后面可以跟 # 注释），或以引号开头却没在本行闭合，都说明值还在后面几行（多行对象、
    每行带前缀的日志、折行的头、PEM 正文、YAML 块），此时要遮蔽输出的其余部分。"""
    value = value.strip()
    if not value or value[0] in "{[(" or value[-1] in ",\\{[(:" \
            or re.fullmatch(r"[|>](?:[+-]?\d?|\d[+-])(?:\s+#.*)?", value):
        return False
    quoted = re.match(r"""\\*(["'])""", value)
    return not quoted or bool(re.search(r"(?<!\\)" + quoted.group(1), value[quoted.end():]))


def _redact_json(value: Any, sensitive: bool = False) -> Any:
    """JSON 结构按键名脱敏：疑似凭据的键下面的字符串（含嵌套的）换成 <redacted>，数字、布尔与 null 保留，
    所以 tokenCount、hasApiKey 这类元信息不受影响；其余字符串继续 redact_secrets（可能是嵌套的 JSON）。"""
    if isinstance(value, dict):
        return {key: _redact_json(item, sensitive or (isinstance(key, str) and bool(_SECRET_KEY_RE.match(key))))
                for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_json(item, sensitive) for item in value]
    if isinstance(value, str):
        return "<redacted>" if sensitive and value else redact_secrets(value)
    return value


#: 孤立的代理码点：原文里转义的 `\ud800` 解码后是这样的字符，按 UTF-8 写不出去，重新写出时要恢复成转义。
_SURROGATE_RE = re.compile("[%s-%s]" % (chr(0xD800), chr(0xDFFF)))


def _json_spans(text: str) -> List[Tuple[int, int, str]]:
    """文本里嵌着的 JSON 对象或数组（例如 `error: { … }`，可以跨行）：[(起点, 终点, 按结构脱敏后的 JSON)]。

    候选起点一次定位，并且只在像 JSON 开头的位置尝试解析（`{` 后面是引号或 `}`，`[` 后面是值或 `]`；数字开头时
    要紧接逗号或 `]`，所以 `[2026-09-23 12:34:56]` 这样的时间戳不算）：解析失败时，标准库会从文本开头数行号，
    `[INFO]` 这样的日志逐个尝试会变成平方级耗时。解析或按结构脱敏失败（包括嵌套太深）的就跳过，交给文本规则。"""
    decoder = json.JSONDecoder()
    spans: List[Tuple[int, int, str]] = []
    covered = 0
    number = r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\s*[,\]]"
    for candidate in re.finditer(r"""\{(?=\s*["}])|\[(?=\s*(?:[\[{"\]]|%s|true\b|false\b|null\b))""" % number, text):
        j = candidate.start()
        if j < covered:
            continue
        try:
            value, end = decoder.raw_decode(text, j)
            if not isinstance(value, (dict, list)):
                continue
            # 一律按脱敏后的结构重新写出，不照抄原文：重复的键解码后只剩最后一个值，原文里前面的值可能就是凭据
            rendered = _SURROGATE_RE.sub(lambda m: chr(92) + "u%04x" % ord(m.group(0)),
                                         json.dumps(_redact_json(value), ensure_ascii=False))
        except (ValueError, RecursionError):
            continue
        spans.append((j, end, rendered))
        covered = end
    return spans


def redact_secrets(text: str) -> str:
    """把疑似凭据替换成 <redacted>。用于写进 doctor、预检与 smoke 结果的外部命令输出。

    先去掉 ANSI 样式；文本里嵌着的 JSON 对象或数组按结构处理（见 _redact_json）；其余按文本处理：PEM 私钥整块，
    Bearer 与常见令牌前缀，疑似凭据的键（含 Authorization、API key）后面的值一直遮到行尾，连同缩进的续行；值在本行
    确定不了结束时，遮蔽这条输出的其余部分。原始记录不改动：派遣的事件流与 stderr
    在本机被 Git 忽略的 .agent/runs/ 中；smoke 的原始日志在系统临时目录的 pi-smoke-* 中，成功且没有 --keep 时删除。
    """
    # 占位符用 NUL 包住编号：原文中的 NUL 先去掉，免得与占位符混淆。
    text = strip_ansi(text).replace(chr(0), "")
    # 嵌着的 JSON 先按结构脱敏并换成占位符，逐行规则只作用于其余文本，免得把 tokenCount 这类元信息也遮掉；
    # JSON 正好是某个疑似凭据的值时（例如 `password: {…}`），占位符随值一起被遮掉。
    saved: List[str] = []
    pieces, last = [], 0
    for start, end, rendered in _json_spans(text):
        pieces.append(text[last:start] + chr(0) + str(len(saved)) + chr(0))
        saved.append(rendered)
        last = end
    text = "".join(pieces) + text[last:]
    text = _SECRET_PEM_RE.sub("<redacted>", text)
    text = _SECRET_TOKEN_RE.sub("<redacted>", text)
    out, last = [], 0
    for match in _SECRET_KV_RE.finditer(text):
        out.append(text[last:match.start()] + match.group(1) + "<redacted>")
        last = match.end()
        if not _value_ends_on_line(match.group(2)):
            last = len(text)  # 值在本行确定不了结束：遮蔽这条输出的其余部分
            break
    text = "".join(out) + text[last:]
    return re.sub(chr(0) + r"(\d+)" + chr(0), lambda m: saved[int(m.group(1))], text)


def redact_obj(value: Any) -> Any:
    """对 JSON 结构中的每个字符串做 redact_secrets：doctor、预检与 smoke 的结果写出之前统一经过这里。"""
    if isinstance(value, str):
        return redact_secrets(value)
    if isinstance(value, list):
        return [redact_obj(item) for item in value]
    if isinstance(value, dict):
        return {key: redact_obj(item) for key, item in value.items()}
    return value


def pi_preflight(pi_cmd: List[str], cwd: Path, executor: Dict[str, Any], out_dir: Path,
                 env: Dict[str, str]) -> Dict[str, Any]:
    """运行模型之前核对：参数支持、思考级别、工具名、版本、模型存在与凭据就绪。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    problems: List[str] = []
    notes: List[str] = []
    code, out, err = run_capture(pi_cmd + RESOURCE_FLAGS + ["--help"], cwd, env, timeout=90)
    (out_dir / "pi-help.txt").write_text(redact_secrets(strip_ansi(out + err)), encoding="utf-8")
    info = parse_help(out + err)
    if code != 0:
        problems.append("pi --help 退出码 %s：%s" % (code, redact_secrets((err or out).strip())[:300]))
    required = list(REQUIRED_PI_FLAGS)
    if executor.get("context_files") == "none":
        required.append("--no-context-files")
    missing = [flag for flag in required if flag not in info["flags"]]
    if missing:
        problems.append("本机 pi 不支持参数：%s" % ", ".join(missing))
    if executor["thinking"] not in info["thinking_levels"]:
        problems.append("思考级别 %s 不在本机 pi 支持列表 %s 中（Pi 对无效值只警告并忽略）"
                        % (executor["thinking"], info["thinking_levels"]))
    if info["builtin_tools"]:
        unknown = [t for t in executor["tools"] if t not in info["builtin_tools"]]
        if unknown:
            problems.append("本机 pi 没有这些内置工具：%s（Pi 会静默忽略未知工具名）" % ", ".join(unknown))
    code, version_out, err = run_capture(pi_cmd + ["--version"], cwd, env, timeout=60)
    version_text = redact_secrets((version_out or err).strip())
    (out_dir / "pi-version.txt").write_text(version_text + "\n", encoding="utf-8")
    version = parse_version(version_text)
    if code != 0 or not version:
        problems.append("无法读取 pi 版本：%s" % version_text[:200])
    elif version < MIN_PI_VERSION:
        notes.append("pi %s 低于 %s，缺少 agent_settled 事件；将退回用 agent_end 判断结束"
                     % (version_text, ".".join(map(str, MIN_PI_VERSION))))
    provider, model = executor["provider"], executor["model"]
    code, out, err = run_capture(pi_cmd + RESOURCE_FLAGS + ["--list-models", model], cwd, env, timeout=90)
    (out_dir / "list-models.txt").write_text(redact_secrets(strip_ansi(out + err)), encoding="utf-8")
    rows = list_models_rows(out)
    if code != 0:
        problems.append("pi --list-models 失败：%s" % redact_secrets((err or out).strip())[:300])
    elif (provider, model) not in rows:
        problems.append("模型 %s/%s 不在本机可用模型列表中（可能是拼写错误、缺少凭据或未在 models.json 定义；"
                        "Pi 对未知模型可能只警告并按自定义 ID 发送）" % (provider, model))
    help_text = (out_dir / "pi-help.txt").read_text(encoding="utf-8")
    if re.search(r"\bpi auth\b", help_text):
        code, out, err = run_capture(pi_cmd + ["auth", "check", "--provider", provider, "--model", model, "--json"],
                                     cwd, env, timeout=90)
        (out_dir / "auth-check.json").write_text(redact_secrets(out if out.strip() else err), encoding="utf-8")
        if code != 0:
            problems.append("pi auth check 未就绪（退出码 %s）：%s" % (code, redact_secrets((out or err).strip())[:300]))
    else:
        notes.append("本机 pi 没有 auth 子命令，跳过凭据检查")
    result = redact_obj({"checked_at": utc_now(), "pi_command": pi_cmd, "pi_version": version_text,
                         "help": info, "problems": problems, "notes": notes, "ok": not problems})
    write_json(out_dir / "preflight.json", result)
    return result


# ---------------------------------------------------------------------------
# 事件流摘要
# ---------------------------------------------------------------------------

USAGE_KEYS = ("input", "output", "cacheRead", "cacheWrite", "totalTokens")
QUIET_EVENTS = ("message_update", "tool_execution_update", "queue_update", "bash_execution_update",
                "entry_appended", "session_info_changed", "thinking_level_changed")
WORK_EVENTS = ("agent_start", "turn_start", "message_start", "tool_execution_start")


def _add_usage(totals: Dict[str, Any], usage: Any) -> None:
    if not isinstance(usage, dict):
        return
    for key in USAGE_KEYS:
        value = usage.get(key)
        if isinstance(value, (int, float)):
            totals[key] += value
    cost = usage.get("cost")
    total = cost.get("total") if isinstance(cost, dict) else None
    if isinstance(total, (int, float)) and total > 0:
        totals["cost_total"] += total
    elif (usage.get("totalTokens") or 0) > 0:
        totals["priced_missing"] += 1


def _message_text(message: Dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(part.get("text", "") for part in content
                         if isinstance(part, dict) and part.get("type") == "text")
    return ""


def ambiguity_domain_words(plan_text: str) -> List[str]:
    """合同正文把哪些“歧义”类词当作领域用语（例如对齐任务的状态 ambiguous、“短句重复歧义”）。

    停止条件与禁止事项之外出现两次及以上的词算领域用语：执行器推理里的这些词多半在说领域概念，
    不代表执行器认为合同有歧义。停止条件中“合同前后矛盾时停止”一类的写法不计入。
    """
    sections = re.split(r"(?m)^(?=## )", plan_text)
    body = "\n".join(s for s in sections if not re.match(r"## +(?:Stop conditions|Forbidden|停止条件|禁止)", s, re.I))
    counts: Dict[str, int] = {}
    for match in AMBIGUITY_RE.finditer(body):
        key = match.group(0).lower()
        counts[key] = counts.get(key, 0) + 1
    return sorted(k for k, n in counts.items() if n >= 2)


def ambiguity_mentions(message: Dict[str, Any], line_no: int,
                       skip_words: Sequence[str] = ()) -> List[Dict[str, Any]]:
    """在一条 assistant 消息的正文与推理中查找“歧义 / 矛盾”一类说法，返回摘录。

    同一段落里相邻的几处只记一次；前面紧跟否定词的（如 no ambiguity、没有矛盾）不算；关键词后面直接跟着
    独立的否定答案的（inconsistencies: none found.、矛盾：无。、报告标题下一行的“未发现。”）不算；其余一律
    保留，包括只是在检查的句子：靠上下文判断“只是在检查”总能被构造的句子绕过，提示本身写明了可能只是在检查；
    附近没有提到合同、规范、步骤或要求的不算；skip_words 中的词（合同自己的领域用语）不算。
    """
    skip = {w.lower() for w in skip_words}
    found: List[Dict[str, Any]] = []
    content = message.get("content")
    blocks = [{"type": "text", "text": content}] if isinstance(content, str) else content
    if not isinstance(blocks, list):
        return found
    for block in blocks:
        if not isinstance(block, dict):
            continue
        kind = block.get("type")
        body = block.get("text") if kind == "text" else block.get("thinking") if kind == "thinking" else None
        if not isinstance(body, str):
            continue
        covered = -1
        for match in AMBIGUITY_RE.finditer(body):
            if match.start() < covered or match.group(0).lower() in skip:
                continue
            negated = AMBIGUITY_NEGATION_RE.search(body[max(0, match.start() - 24):match.start()]) \
                and not AMBIGUITY_DOUBLE_NEGATION_RE.search(body[max(0, match.start() - 80):match.start()])
            if negated or AMBIGUITY_RESOLVED_RE.search(body[match.end():match.end() + 80]):
                continue
            if not AMBIGUITY_CONTEXT_RE.search(body[max(0, match.start() - 240):match.end() + 240]):
                continue
            start, end = max(0, match.start() - 100), min(len(body), match.end() + 140)
            covered = end
            found.append({"line": line_no, "kind": kind, "keyword": match.group(0),
                          "excerpt": " ".join(body[start:end].split())[:260]})
    return found


def summarize_events(events_path: Path, work_dir: Path, executor: Dict[str, Any],
                     stderr_path: Optional[Path] = None,
                     expects_settled: Optional[bool] = None,
                     allowed_outside: Sequence[Path] = (),
                     plan_text: str = "") -> Tuple[Dict[str, Any], str]:
    """解析 JSONL 事件流。返回（摘要, 最终 assistant 文本）。进程退出码不代表任务成功。

    expects_settled：已知 pi 版本会输出 agent_settled（≥ 0.80.4）时为 True，此时只有 agent_end 不算完成。
    allowed_outside：worktree 之外、允许执行器访问的目录（本 attempt 的运行目录，其中有随消息附上的
    plan.md 与 instruction.md）；访问这些目录只记入 own_run_paths，不算工作副本外访问。
    plan_text：本 attempt 的 plan.md，用来排除合同本身的领域用语（见 ambiguity_domain_words）。
    """
    data = events_path.read_bytes() if events_path.exists() else b""
    own_path_forms = _path_forms([work_dir] + list(allowed_outside))
    lines = data.split(b"\n")
    counts: Dict[str, int] = {}
    parse_errors: List[int] = []
    header: Optional[Dict[str, Any]] = None
    assistant: List[Dict[str, Any]] = []
    totals: Dict[str, Any] = {k: 0 for k in USAGE_KEYS}
    totals.update({"cost_total": 0.0, "priced_missing": 0})
    tool_counts: Dict[str, int] = {}
    tool_errors = 0
    commands: List[str] = []
    suspicious: List[Dict[str, Any]] = []
    temp_paths: List[Dict[str, Any]] = []
    cache_cleanups: List[Dict[str, Any]] = []
    outside_paths: List[Dict[str, Any]] = []
    outside_by_call: Dict[str, Dict[str, Any]] = {}
    own_run_paths: List[Dict[str, str]] = []
    mentions: List[Dict[str, Any]] = []
    domain_words = ambiguity_domain_words(plan_text)
    allowed_roots = [Path(p).resolve() for p in allowed_outside]
    retries: List[Dict[str, Any]] = []
    compactions = 0
    system_sections: List[str] = []
    agent_end_count = 0
    settled_count = 0
    last_will_retry: Optional[bool] = None
    pending_work = False
    work_root = work_dir.resolve()
    for number, raw in enumerate(lines, 1):
        if not raw.strip():
            continue
        try:
            event = json.loads(raw.rstrip(b"\r").decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            parse_errors.append(number)
            continue
        if not isinstance(event, dict):
            parse_errors.append(number)
            continue
        kind = str(event.get("type"))
        counts[kind] = counts.get(kind, 0) + 1
        if kind in WORK_EVENTS:
            pending_work = True
        if kind == "session" and header is None:
            header = {k: event.get(k) for k in ("version", "id", "timestamp", "cwd")}
        elif kind == "message_end":
            message = event.get("message") if isinstance(event.get("message"), dict) else {}
            role = message.get("role")
            if role == "assistant":
                for item in ambiguity_mentions(message, number, domain_words):
                    item["message"] = len(assistant)
                    mentions.append(item)
                assistant.append(message)
                _add_usage(totals, message.get("usage"))
            elif role == "toolResult":
                _add_usage(totals, message.get("usage"))
            elif role == "system" and isinstance(message.get("sections"), dict):
                system_sections = sorted(message["sections"].keys())
        elif kind == "entry_appended":
            entry = event.get("entry") if isinstance(event.get("entry"), dict) else {}
            if entry.get("type") == "usage":
                _add_usage(totals, entry.get("usage"))
        elif kind == "compaction_end":
            compactions += 1
            result = event.get("result") if isinstance(event.get("result"), dict) else {}
            _add_usage(totals, result.get("usage"))
        elif kind == "tool_execution_start":
            name = str(event.get("toolName"))
            tool_counts[name] = tool_counts.get(name, 0) + 1
            args = event.get("args") if isinstance(event.get("args"), dict) else {}
            if name in ("bash", "powershell"):
                command = str(args.get("command", ""))
                commands.append(command[:500])
                scan = _mask_paths(command, own_path_forms)
                # Keep each distinct excerpt: an early mktemp must not hide a later
                # fixed path, even on the same long line. This is review evidence,
                # not shell parsing or a claim that cleanup was safe.
                for match_line, scan_line in enumerate(scan.splitlines(), 1):
                    excerpts = set()
                    for temp_found in TEMP_PATH_RE.finditer(scan_line):
                        excerpt = _match_excerpt(scan_line, temp_found.start(), temp_found.end())
                        if excerpt not in excerpts:
                            excerpts.add(excerpt)
                            temp_paths.append({"event_line": number, "match": excerpt,
                                               "match_line": match_line})
                for pattern, label in SUSPICIOUS_COMMANDS:
                    found = re.search(pattern, command, re.I)
                    if not found:
                        continue
                    if label == DELETE_LABEL:
                        cleanup = _cache_dir_cleanup(command)
                        if cleanup:
                            cache_cleanups.append({"event_line": number, "command": cleanup[:200]})
                            continue
                    # 记下命中所在的行：长命令的开头往往看不出问题在哪里。
                    suspicious.append({"label": label, "command": command[:300], "event_line": number,
                                       "match": _match_excerpt(command, found.start(), found.end()),
                                       "match_line": command.count("\n", 0, found.start()) + 1,
                                       "command_lines": command.count("\n") + 1})
                    break
            for key in ("path", "file_path"):
                value = args.get(key)
                if isinstance(value, str) and value.strip():
                    candidate = Path(os.path.expanduser(value.strip()))
                    resolved = (candidate if candidate.is_absolute() else work_root / candidate).resolve()
                    if is_within(resolved, work_root):
                        continue
                    if any(is_within(resolved, root) for root in allowed_roots):
                        own_run_paths.append({"tool": name, "path": value[:300]})
                        continue
                    record = {"tool": name, "path": value[:300], "exists": resolved.exists(), "failed": None}
                    outside_paths.append(record)
                    call_id = event.get("toolCallId")
                    if isinstance(call_id, str):
                        outside_by_call[call_id] = record
        elif kind == "tool_execution_end":
            if event.get("isError"):
                tool_errors += 1
            record = outside_by_call.pop(str(event.get("toolCallId")), None)
            if record is not None:
                record["failed"] = bool(event.get("isError"))
        elif kind == "agent_end":
            agent_end_count += 1
            last_will_retry = bool(event.get("willRetry"))
            if not last_will_retry and settled_count == 0:
                pending_work = False
        elif kind == "agent_settled":
            settled_count += 1
            pending_work = False
        elif kind == "auto_retry_start":
            retries.append({"attempt": event.get("attempt"),
                            "error": redact_secrets(str(event.get("errorMessage", "")))[:300]})
        elif kind == "auto_retry_end" and not event.get("success"):
            retries.append({"final_error": redact_secrets(str(event.get("finalError", "")))[:300]})

    truncated = bool(data) and not data.endswith(b"\n")
    if settled_count:
        terminal = "agent_settled"
        complete = not pending_work
    elif agent_end_count:
        terminal = "agent_end"
        # 支持 agent_settled 的版本必须以它结束；只在明确不支持时才用 agent_end 降级判断。
        complete = expects_settled is False and not pending_work and last_will_retry is False
    else:
        terminal = None
        complete = False
    final = assistant[-1] if assistant else {}
    final_text = _message_text(final) if final else ""
    # 最后一条消息的正文就是执行报告：报告里写到的矛盾由 contract_conflicts 等字段承载，不算“未声明的提及”。
    mentions = [m for m in mentions if not (m["message"] == len(assistant) - 1 and m["kind"] == "text")]
    requested = (executor.get("provider"), executor.get("model"))
    actual = sorted({(str(m.get("provider")), str(m.get("model"))) for m in assistant})
    response_models = sorted({str(m.get("responseModel")) for m in assistant if m.get("responseModel")})
    provider_levels = sorted({str(m.get("providerThinkingLevel")) for m in assistant
                              if m.get("providerThinkingLevel")})
    model_match = bool(assistant) and all(pair == requested for pair in actual)
    stderr_flags: List[str] = []
    if stderr_path is not None and stderr_path.exists():
        stderr_text = strip_ansi(stderr_path.read_text(encoding="utf-8", errors="replace"))
        stderr_flags = [name for name, pattern in STDERR_WARNING_PATTERNS if re.search(pattern, stderr_text)]
    stop_reason = final.get("stopReason") if final else None
    cost_status = "unknown"
    if assistant and totals["cost_total"] > 0:
        cost_status = "estimated" if totals["priced_missing"] == 0 and compactions == 0 else "partial"
    requested_thinking = executor.get("thinking")
    problems: List[str] = []
    if not data:
        problems.append("事件流为空")
    if parse_errors:
        problems.append("事件流有 %d 行无法解析" % len(parse_errors))
    if truncated:
        problems.append("事件流最后一行不完整（可能被截断）")
    if not complete:
        if agent_end_count and not settled_count and expects_settled is not False:
            problems.append("没有 agent_settled：该 pi 版本应以它结束，事件流可能被截断或运行被中断")
        else:
            problems.append("没有观察到完整的结束事件（agent_settled / agent_end）")
    mismatched_levels = [level for level in provider_levels if level != requested_thinking]
    if mismatched_levels:
        problems.append("提供商报告的思考级别 %s 与要求的 %s 不一致" % (mismatched_levels, requested_thinking))
    if stop_reason != "stop":
        problems.append("最终 assistant stopReason=%s" % stop_reason)
    if final.get("errorMessage"):
        problems.append("最终 assistant 错误：%s" % redact_secrets(str(final.get("errorMessage")))[:300])
    textual_call = TEXTUAL_TOOL_CALL_RE.search(final_text or "")
    if textual_call:
        problems.append("最终 assistant 消息的正文里有未执行的工具调用（%s）：模型把工具调用写成了文本，Pi 没有执行，"
                        "回合随之结束，运行没有做完" % textual_call.group(0))
    if not model_match:
        problems.append("实际模型 %s 与要求 %s 不一致或缺失" % (actual, "/".join(map(str, requested))))
    for flag in ("custom_model_id", "invalid_thinking", "unknown_option"):
        if flag in stderr_flags:
            problems.append("stderr 出现 %s 警告" % flag)
    summary = {
        "lines": sum(1 for line in lines if line.strip()),
        "event_counts": counts,
        "parse_error_lines": parse_errors[:50],
        "truncated": truncated,
        "session_header": header,
        "terminal_event": terminal,
        "complete": complete,
        "final_stop_reason": stop_reason,
        "final_error": redact_secrets(str(final["errorMessage"])) if final and final.get("errorMessage") else None,
        "requested_model": {"provider": requested[0], "model": requested[1], "thinking": requested_thinking},
        "actual_models": [{"provider": p, "model": m} for p, m in actual],
        "response_models": response_models,
        "provider_thinking_levels": provider_levels,
        "thinking_evidence": ("provider_reported" if provider_levels else
                              "not_reported：该协议或配置不回报 providerThinkingLevel，只能确认请求的级别；"
                              "实际发送形式取决于协议（例如 anthropic-messages 预算模式把 high 映射为 thinking 预算）"),
        "model_match": model_match,
        "assistant_messages": len(assistant),
        "tool_calls": tool_counts,
        "tool_errors": tool_errors,
        "auto_retries": retries,
        "compactions": compactions,
        "system_prompt_sections": system_sections,
        "usage": {k: totals[k] for k in USAGE_KEYS},
        # 未知费用记为 null 而不是 0；partial 时 total 只是已知部分的下界。
        "cost": {"total": round(totals["cost_total"], 6) if cost_status != "unknown" else None,
                 "status": cost_status, "unpriced_messages": totals["priced_missing"],
                 "note": "Pi 按模型目录价格估算；以提供商或网关账单为准"},
        "stderr_flags": stderr_flags,
        "shell_commands": commands[:200],
        "suspicious_commands": suspicious[:100],
        "temp_path_uses": temp_paths[:50],
        "temp_path_use_count": len(temp_paths),
        "cache_dir_cleanups": cache_cleanups[:50],
        "outside_worktree_paths": outside_paths[:100],
        "own_run_paths": own_run_paths[:50],
        "ambiguity_mention_count": len(mentions),
        "ambiguity_domain_words": domain_words,
        "ambiguity_mentions": mentions[:20],
        "problems": problems,
        "ok": not problems,
    }
    return summary, final_text


def extract_report(final_text: str, run_dir: Path) -> Dict[str, Any]:
    if not final_text.strip():
        return {"status": "missing"}
    write_text(run_dir / "executor-report.md", final_text if final_text.endswith("\n") else final_text + "\n",
               exclusive=False)
    blocks = re.findall(r"```json\s*\n(.*?)\n```", final_text, re.S)
    if not blocks:
        return {"status": "no_json", "path": "executor-report.md"}
    try:
        data = json.loads(blocks[-1])
    except ValueError as exc:
        return {"status": "json_invalid", "error": str(exc), "path": "executor-report.md"}
    write_json(run_dir / "executor-report.json", data)
    fields = data if isinstance(data, dict) else {}
    counted = {key: len(fields[key]) if isinstance(fields.get(key), list) else 0
               for key in ("contract_conflicts", "unresolved_questions")}
    return dict({"status": "json_ok", "executor_status": fields.get("executor_status"),
                 "path": "executor-report.json"}, **counted)


# ---------------------------------------------------------------------------
# 候选、范围与复审提示
# ---------------------------------------------------------------------------

def evaluate_scope(changes: List[Dict[str, str]], contract: Dict[str, Any], head_after: str,
                   base: str, extra_protected: Sequence[str] = ()) -> Dict[str, Any]:
    scope = contract["scope"]
    exact_allowed = set(scope["allowed_modified_files"]) | set(scope["allowed_new_files"])
    allowed = {"A": compile_patterns(scope["allowed_new_files"]),
               "D": compile_patterns(scope["allowed_deleted_files"])}
    allowed_modified = compile_patterns(scope["allowed_modified_files"])
    forbidden = compile_patterns(scope["forbidden_paths"])
    protected = compile_patterns(list(PROTECTED_PATTERNS) + list(extra_protected), ignore_case=True)
    dependency = compile_patterns(DEPENDENCY_PATTERNS)
    sensitive = compile_patterns(SENSITIVE_PATTERNS)
    violations: List[Dict[str, str]] = []
    warnings: List[Dict[str, str]] = []
    files: List[Dict[str, str]] = []
    for change in changes:
        path, status = change["path"], change["status"]
        verdict = "in_scope"
        if change.get("path_decode_error") or has_control_chars(path):
            # 替换解码后的名字不能用来做授权判断
            violations.append({"path": repr(path), "kind": "invalid_path",
                               "detail": "路径含控制字符或不是合法 UTF-8"})
            files.append({"path": repr(path), "status": status, "scope": "violation"})
            continue
        if matches(protected, path):
            violations.append({"path": path, "kind": "protected_path", "detail": "合同、证据、代理规则或调度器文件"})
            verdict = "violation"
        elif matches(forbidden, path):
            violations.append({"path": path, "kind": "forbidden_path", "detail": "命中 forbidden_paths"})
            verdict = "violation"
        elif not matches(allowed.get(status, allowed_modified), path):
            violations.append({"path": path, "kind": "out_of_scope", "detail": "状态 %s 不在允许集合" % status})
            verdict = "violation"
        if change["new_mode"] == "120000":
            violations.append({"path": path, "kind": "symlink", "detail": "新增或改为符号链接"})
            verdict = "violation"
        if "160000" in (change["new_mode"], change["old_mode"]):
            violations.append({"path": path, "kind": "submodule", "detail": "子模块或嵌入仓库变化"})
            verdict = "violation"
        if status in ("M", "T") and change["old_mode"] != change["new_mode"] \
                and "120000" not in (change["old_mode"], change["new_mode"]):
            warnings.append({"path": path, "kind": "mode_changed",
                             "detail": "%s -> %s" % (change["old_mode"], change["new_mode"])})
        if matches(dependency, path) and scope["dependency_changes"] == "forbidden":
            if path in exact_allowed:
                warnings.append({"path": path, "kind": "dependency_manifest_changed",
                                 "detail": "合同允许修改此文件，但禁止依赖变更：需人工确认"})
            else:
                violations.append({"path": path, "kind": "dependency_change", "detail": "合同禁止依赖变更"})
                verdict = "violation"
        if matches(sensitive, path):
            warnings.append({"path": path, "kind": "sensitive_file", "detail": "测试/CI/构建或环境配置被修改"})
        files.append({"path": path, "status": status, "scope": verdict})
    actions = contract["authorization"]["executor"]
    if head_after != base:
        item = {"path": "HEAD", "kind": "head_moved", "detail": "执行器改变了 HEAD（%s）" % head_after[:12]}
        (warnings if "local_commit" in actions else violations).append(item)
    counts = {s: sum(1 for c in changes if c["status"] == s) for s in ("A", "M", "D", "T")}
    return {"files": files, "counts": counts, "violations": violations, "warnings": warnings,
            "ok": not violations}


def review_hints(patch_path: Path) -> Dict[str, Any]:
    added: List[str] = []
    removed: List[str] = []
    with open(patch_path, "rb") as handle:
        data = handle.read(20 * 1024 * 1024)
    for line in data.decode("utf-8", "replace").splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            added.append(line[1:])
        elif line.startswith("-") and not line.startswith("---"):
            removed.append(line[1:])
    return {
        "skip_markers_added": [line.strip()[:200] for line in added if SKIP_MARKER_RE.search(line)][:50],
        "assertion_lines_added": sum(1 for line in added if ASSERT_RE.search(line)),
        "assertion_lines_removed": sum(1 for line in removed if ASSERT_RE.search(line)),
        "patch_truncated_for_hints": len(data) >= 20 * 1024 * 1024,
    }


def record_candidate(repo: Repo, run_dir: Path, work_dir: Path, base: str) -> Dict[str, Any]:
    """固定候选：树对象 ID + 完整二进制补丁，并做补丁往返校验。"""
    meta = read_json_or(run_dir / "meta.json", {})
    tree = snapshot_tree(work_dir, base, run_dir, "candidate", meta.get("git_autocrlf"))
    patch_path = run_dir / "candidate.patch"
    with open(patch_path, "xb") as handle:
        handle.write(git(["diff", "--binary", "--no-ext-diff", "--no-textconv", "--no-renames", "--full-index",
                          base, tree], work_dir).stdout)
    stat = git(["diff", "--stat", "--no-ext-diff", "--no-textconv", "--no-renames", base, tree], work_dir).stdout
    (run_dir / "candidate.stat.txt").write_bytes(stat)
    try:
        roundtrip = tree_from_patch(repo.root, base, patch_path, run_dir, meta.get("git_autocrlf"))
        verified = roundtrip == tree
    except DispatchError as exc:
        roundtrip, verified = "error: %s" % exc, False
    return {"tree": tree, "base": base, "patch": "candidate.patch", "patch_sha256": sha256_file(patch_path),
            "patch_bytes": patch_path.stat().st_size, "patch_roundtrip_verified": verified,
            "roundtrip_tree": roundtrip, "recorded_at": utc_now()}


# ---------------------------------------------------------------------------
# Attempt 目录与状态
# ---------------------------------------------------------------------------

def set_state(run_dir: Path, state: str, **info: Any) -> None:
    record = {"state": state, "at": utc_now()}
    record.update(info)
    with open(run_dir / "history.jsonl", "a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    write_json(run_dir / "state.json", record)


def log_event(run_dir: Path, event: str, **info: Any) -> None:
    record = {"event": event, "at": utc_now()}
    record.update(info)
    with open(run_dir / "history.jsonl", "a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def get_state(run_dir: Path) -> str:
    return str(read_json_or(run_dir / "state.json", {}).get("state", "UNKNOWN"))


def task_attempts(repo: Repo, task_id: str) -> List[Path]:
    base = repo.runs_dir / task_id
    if not base.is_dir():
        return []
    found = [d for d in base.iterdir() if d.is_dir() and ATTEMPT_DIR_RE.match(d.name)]
    return sorted(found, key=lambda d: int(ATTEMPT_DIR_RE.match(d.name).group("n")))  # type: ignore[union-attr]


def budget_usage(repo: Repo, task_id: str, exclude: Optional[Path] = None) -> Dict[str, Any]:
    started = 0
    wall = 0.0
    for attempt in task_attempts(repo, task_id):
        if exclude is not None and norm_case(str(attempt)) == norm_case(str(exclude)):
            continue
        if (attempt / "claim").is_dir():
            started += 1
            run = read_json_or(attempt / "run.json", None)
            if run is not None and run.get("wall_seconds") is not None:
                wall += float(run["wall_seconds"])
            else:  # 仍在运行或调度器中途退出：按领取时预留的时限计入
                reservation = read_json_or(attempt / "claim" / "reservation.json", {})
                wall += float(reservation.get("timeout_seconds") or 0)
    return {"attempts_started": started, "wall_seconds_used": round(wall, 3)}


class TaskLock:
    """task-id 级互斥锁：预算核算与领取必须在同一临界区完成。"""

    def __init__(self, repo: "Repo", task_id: str, wait_seconds: float = 30.0, stale_seconds: float = 300.0) -> None:
        self.path = repo.runs_dir / task_id / ".task.lock"
        self.wait_seconds = wait_seconds
        self.stale_seconds = stale_seconds

    def __enter__(self) -> "TaskLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.wait_seconds
        while True:
            try:
                self.path.mkdir()
                write_text(self.path / "owner.json", json.dumps({"pid": os.getpid(), "at": utc_now()}) + "\n")
                return self
            except FileExistsError:
                try:
                    age = time.time() - self.path.stat().st_mtime
                except OSError:
                    age = 0.0
                if age > self.stale_seconds:  # 临界区只需毫秒级；超过阈值视为持有者已崩溃
                    shutil.rmtree(str(self.path), ignore_errors=True)
                    continue
                if time.monotonic() > deadline:
                    raise DispatchError("任务锁被占用：%s（另一个 run 正在领取；如确认无人使用可删除该目录）"
                                        % self.path)
                time.sleep(0.2)

    def __exit__(self, *_exc: Any) -> None:
        shutil.rmtree(str(self.path), ignore_errors=True)


def allocate_attempt(repo: Repo, task_id: str) -> Tuple[Path, int]:
    base = repo.runs_dir / task_id
    base.mkdir(parents=True, exist_ok=True)
    existing = [int(ATTEMPT_DIR_RE.match(d.name).group("n")) for d in base.iterdir()  # type: ignore[union-attr]
                if d.is_dir() and ATTEMPT_DIR_RE.match(d.name)]
    number = max(existing, default=0) + 1
    for _ in range(1000):
        candidate = base / ("attempt-%03d" % number)
        try:
            candidate.mkdir()
            return candidate, number
        except FileExistsError:
            number += 1
    raise DispatchError("无法分配 attempt 目录")


def resolve_run_dir(repo: Repo, value: str) -> Path:
    """接受 attempt 路径、task-id/attempt-NNN、task-id 或 task-id.vN（取最新 attempt）。"""
    candidates = [Path(value), repo.runs_dir / value]
    key = PLAN_KEY_RE.match(value)
    task_id = key.group("task") if key else (value if TASK_ID_RE.match(value) else None)
    for candidate in candidates:
        if (candidate / "meta.json").is_file():
            resolved = candidate.resolve()
            if not is_within(resolved, repo.runs_dir):
                raise DispatchError("attempt 目录必须位于 %s 下" % repo.runs_dir, EXIT_USAGE)
            return resolved
    if task_id:
        attempts = task_attempts(repo, task_id)
        if key:
            attempts = [a for a in attempts
                        if read_json_or(a / "meta.json", {}).get("plan_version") == int(key.group("ver"))]
        if attempts:
            return attempts[-1].resolve()
    raise DispatchError("找不到 attempt：%s" % value, EXIT_USAGE)


def load_attempt(repo: Repo, run_dir: Path) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    meta = read_json(run_dir / "meta.json")
    contract = normalize_contract(read_json(run_dir / "contract.json"))
    return meta, contract


def verify_inputs(run_dir: Path, meta: Dict[str, Any]) -> List[str]:
    problems = []
    for name, key in (("plan.md", "plan_md_sha256"), ("contract.json", "contract_json_sha256")):
        path = run_dir / name
        if not path.exists() or sha256_file(path) != meta.get(key):
            problems.append("%s 的哈希与 prepare 时记录的不一致" % name)
    return problems


def resolve_executor(contract: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    executor = dict(contract["executor"])
    for field, env_name in (("provider", "PI_EXEC_PROVIDER"), ("model", "PI_EXEC_MODEL"),
                            ("thinking", "PI_EXEC_THINKING")):
        env_value = os.environ.get(env_name)
        if not env_value:
            continue
        explicit = contract.get("_raw_executor", {}).get(field)
        if explicit and explicit != env_value:
            raise DispatchError("%s=%s 与合同 executor.%s=%s 冲突；以审阅过的合同为准，请移除环境变量"
                                % (env_name, env_value, field, explicit), EXIT_USAGE)
        if not explicit:
            executor[field] = env_value
    for field in ("provider", "model"):
        value = executor.get(field)
        if not value or not MODEL_TOKEN_RE.match(str(value)) or PLACEHOLDER_RE.search(str(value)):
            raise DispatchError("缺少或无效的执行模型 %s：在合同 executor 中填写，或设置 PI_EXEC_%s"
                                % (field, field.upper()), EXIT_USAGE)
    if executor.get("thinking") not in FALLBACK_THINKING_LEVELS:
        raise DispatchError("无效的思考级别：%r" % executor.get("thinking"), EXIT_USAGE)
    allowlist = config.get("allowed_executors") or []
    if allowlist:
        hits = [a for a in allowlist if isinstance(a, dict) and a.get("provider") == executor["provider"]
                and a.get("model") == executor["model"]]
        if not hits:
            raise DispatchError("执行模型 %s/%s 不在 .agent/dispatch.config.json 的 allowed_executors 中"
                                % (executor["provider"], executor["model"]), EXIT_BLOCKED)
        pinned = hits[0].get("thinking")
        if pinned and pinned != executor["thinking"]:
            raise DispatchError("该执行模型的思考级别固定为 %s，合同为 %s" % (pinned, executor["thinking"]),
                                EXIT_BLOCKED)
    return executor


def load_raw_executor(run_dir: Path) -> Dict[str, Any]:
    raw = read_json_or(run_dir / "contract.json", {})
    return raw.get("executor", {}) if isinstance(raw, dict) else {}


# ---------------------------------------------------------------------------
# 执行说明
# ---------------------------------------------------------------------------

INSTRUCTION_TEMPLATE = """# 执行说明（调度器生成）

你是本任务的 Pi 执行器。前面附带的 plan.md 是已经审阅的任务合同，本说明只补充运行事实与报告格式；二者冲突时停止并报告。

## 运行事实
- 任务：{task_id} · 合同版本 v{version} · {attempt_id}
- 工作目录：{work_dir}（独立 worktree，基线 {base}）
- 可用工具：{tools}
- 单轮时限：{timeout} 秒，到时会被强制终止，未完成的自检与报告都会丢失。你看不到已用时间：开始时用 shell 记下时间（例如 `date +%s`），之后定期对比。用时过半前应开始修改文件，不要在动手前长时间推演；剩余不到五分之一时停止扩展，先运行检查并写执行报告。

## 必须遵守
1. 只修改合同 Scope 允许的文件；需要越界、需要新增依赖或需要远程写入时，停止并在报告中说明。
2. 不修改合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/ 与 scripts/pi_dispatch.py、scripts/dispatch-pi.sh。
3. 不删除、跳过或弱化测试与断言来获得通过。
4. {commit_rule}不要用 git stash、git checkout -- 或 git reset 临时撤掉自己的改动来对比基线行为：恢复一旦失败，改动就会丢失。确实需要对比时，在报告中说明，由验收端在基线副本上运行。
5. 不访问工作目录之外的路径。唯一的例外是临时文件，只用来存放测试或命令的中间产物：测试框架管理的临时目录（例如 pytest 的 tmp_path）可以使用；确需在命令里新建临时目录时，只能写成 `T=$(mktemp -d)`，并以 `rm -rf "$T"` 作为这条命令的最后一步，不要切换到其中运行命令，也不要读写其他工作目录之外的路径。不读取、打印或写入任何凭据。读写工作目录中的文件一律使用相对路径（工具的当前目录就是工作目录），不要手写绝对路径——手写的长路径容易拼错而落到工作目录之外；`"$T"` 这样运行时生成的临时路径不受此限。plan.md 与本说明已随消息附上，不需要再去读取它们的原始文件。
6. 遇到未定义行为、需求冲突、基线不符或环境缺失：停止并报告，不要猜测。合同内部前后矛盾（例如行为说明、步骤、DoD 或测试要求对同一行为说法不同）也属于需求冲突，不要自行选定一种解释当作完成。其余部分能独立完成时可以继续，但要把两处原文、你暂时采用的做法和理由写进报告的 `contract_conflicts`，并把相关 DoD 标为 blocked。
{self_check_rule}
8. 验收端会在固定候选上做变异检查（mutate），你不需要自己做突变反测；确要临时改坏文件验证测试时，备份放在工作目录内（例如 `x.ts.orig`），同一条命令里改回并删除备份，不要用系统临时目录。
9. 合同要求编写测试时，每个拒绝反例先验证合法基线，再只改受测条件并断言具体错误；避免另一条规则提前拒绝而掩盖缺口。比较摘要时固定其余字段，分别验证每个语义字段；非空、partial 等有不同分支的形态按合同分别覆盖。只从非法输入得到异常、或测试数量增加，不代表目标规则已被保护。
{setup_facts}
## 机器合同摘要（调度器据此判定范围与验收）
以下内容由调度器从机器合同（JSON）自动生成。它与 plan.md 有任何不一致时，停止并在报告中指出，不要自行选择其一。

{machine_summary}

## 最后一条消息必须是执行报告
只输出一份报告：先用中文逐项说明 DoD（{dod_ids}）的完成情况、运行过的自检命令与结果、合同中的矛盾与你的处理、遗留问题与阻塞原因；
然后给出一个 JSON 代码块，字段如下（自检结果属于自述，最终验收由验收端独立完成）。
`contract_conflicts` 的每一项写成 `{{"quotes": ["合同原文 1", "合同原文 2"], "adopted": "暂时采用的做法", "reason": "理由"}}`；没有矛盾时保留空列表：

```json
{{
  "task_id": "{task_id}",
  "plan_version": {version},
  "attempt_id": "{attempt_id}",
  "executor_status": "completed | blocked | partial",
  "changed_files": ["相对路径"],
  "self_checks": [{{"id": "V01", "command": "实际命令", "reported_exit_code": 0, "summary": "关键输出"}}],
  "dod": [{{"id": "D01", "status": "done | not_done | blocked", "note": "说明"}}],
  "contract_conflicts": [],
  "unresolved_questions": [],
  "limitations": []
}}
```
"""


def setup_facts_text(setup_results: Sequence[Dict[str, Any]]) -> str:
    """把 prepare 阶段 setup 的结果写给执行器：它看不到 prepare 的日志，否则只能猜依赖有没有装好。"""
    if not setup_results:
        return ""
    lines = ["", "## 准备阶段已经做过的事（prepare）"]
    for item in setup_results:
        argv = item.get("argv") or []
        command = subprocess.list2cmdline(argv) if IS_WINDOWS else " ".join(shlex_quote(a) for a in argv)
        lines.append("- %s `%s`（cwd %s）：%s，退出码 %s。不必重跑。"
                     % (item.get("id"), command, item.get("cwd", "."), "已通过" if item.get("passed") else "失败",
                        item.get("exit_code")))
    return "\n".join(lines) + "\n"


def render_instruction(meta: Dict[str, Any], contract: Dict[str, Any], executor: Dict[str, Any],
                       timeout: int, extra_protected: Sequence[str] = (),
                       setup_results: Sequence[Dict[str, Any]] = ()) -> str:
    tools = executor["tools"]
    has_shell = bool({"bash", "powershell"} & set(tools))
    actions = contract["authorization"]["executor"]
    commit_rule = ("可以在 worktree 中创建本地提交，但不得推送、合并或部署。" if "local_commit" in actions
                   else "不提交、推送、合并或部署；保持 HEAD 为基线提交。")
    if has_shell and "local_test" in actions:
        ids = ", ".join(c["id"] for c in contract["checks"]) or "（合同未列出）"
        self_check_rule = ("7. 完成后运行合同 Validation commands 中与改动相关的检查（%s），如实记录结果；"
                           "不需要每改一行都跑全量测试。必要检查通过且没有新增修改或未解决问题后，转入执行报告；"
                           "不要自行扩大到无关全仓测试。变异检查（故意改坏实现来检验测试）默认由验收端执行；"
                           "只有合同明确列出变异命令和目标范围时才能运行，local_test 本身不授权额外变异，"
                           "临时修改后恢复也不能突破 Scope。时间不足时报告未运行项与剩余工作，不得声称通过。") % ids
    else:
        self_check_rule = "7. 你没有可用的 shell 工具或未获自检授权：不要声称运行过测试，检查由验收端执行。"
    dod_ids = ", ".join(d.get("id", "?") for d in contract["definition_of_done"])
    return INSTRUCTION_TEMPLATE.format(
        task_id=meta["task_id"], version=meta["plan_version"], attempt_id=meta["attempt_id"],
        work_dir=meta["worktree"], base=meta["base_sha"], tools=",".join(tools), timeout=timeout,
        commit_rule=commit_rule, self_check_rule=self_check_rule, dod_ids=dod_ids,
        setup_facts=setup_facts_text(setup_results),
        machine_summary=machine_summary(contract, extra_protected))


def machine_summary(contract: Dict[str, Any], extra_protected: Sequence[str] = ()) -> str:
    scope = contract["scope"]

    def listing(values: Sequence[str]) -> str:
        return "、".join("`%s`" % v for v in values) if values else "无"

    lines = [
        "- 允许修改：%s" % listing(scope["allowed_modified_files"]),
        "- 允许新增：%s" % listing(scope["allowed_new_files"]),
        "- 允许删除：%s" % listing(scope["allowed_deleted_files"]),
        "- 额外禁止：%s；另外始终禁止合同、代理规则、.agent/、.agents/、.claude/、.codex/、.pi/ 与调度脚本" % listing(scope["forbidden_paths"]),
        "- 本仓库只读的路径：%s" % listing(list(extra_protected)),
        "- 依赖变更：%s" % scope["dependency_changes"],
        "- 执行器授权：%s" % ", ".join(contract["authorization"]["executor"]),
        "- 验收检查（由验收端在固定候选上独立运行）：",
    ]
    base_notes = {
        # 合同 Markdown 写“基线应失败 / 基线应通过”，那是给验收端的说明；执行器按字面读容易误解成
        # “这条检查应该失败”。这里写成完成后的要求。
        "fail": "；基线上预期失败（用来证明修复），你完成后它必须通过",
        "pass": "；基线上已通过（回归保护），完成后仍须通过",
    }
    for check in contract["checks"]:
        lines.append("  - %s%s：`%s`（cwd %s，超时 %ss%s）" % (
            check["id"], "（必要）" if check.get("required", True) else "",
            subprocess.list2cmdline(check["argv"]) if IS_WINDOWS else " ".join(shlex_quote(a) for a in check["argv"]),
            check.get("cwd", "."), check["timeout_seconds"], base_notes.get(check.get("expect_on_base", "any"), "")))
    return "\n".join(lines)


def shlex_quote(value: str) -> str:
    import shlex

    return shlex.quote(value)


# ---------------------------------------------------------------------------
# 摘要
# ---------------------------------------------------------------------------

def write_summary(run_dir: Path, repo: Repo) -> None:
    meta = read_json_or(run_dir / "meta.json", {})
    state = get_state(run_dir)
    run = read_json_or(run_dir / "run.json", {})
    events = read_json_or(run_dir / "events-summary.json", {})
    report = read_json_or(run_dir / "report-status.json", {})
    candidate = read_json_or(run_dir / "candidate.json", {})
    scope = read_json_or(run_dir / "scope.json", {})
    extra = read_json_or(run_dir / "observations.json", {})
    executor = read_json_or(run_dir / "executor.json", {})
    usage = events.get("usage", {})
    cost = events.get("cost", {})
    yes_no = lambda value: "是" if value else "否"  # noqa: E731
    lines = [
        "# Attempt 摘要：%s v%s · %s" % (meta.get("task_id"), meta.get("plan_version"), meta.get("attempt_id")),
        "",
        "- 状态：**%s**" % state,
        "- 基线：`%s`" % meta.get("base_sha"),
        "- 候选树：`%s`（补丁往返校验：%s）" % (candidate.get("tree"), yes_no(candidate.get("patch_roundtrip_verified"))),
        "- 要求的执行模型：%s/%s · thinking=%s · 工具=%s" % (
            executor.get("provider"), executor.get("model"), executor.get("thinking"),
            ",".join(executor.get("tools", []))),
        "- 实际模型：%s（一致：%s）· 提供商回报的思考级别：%s" % (
            ", ".join("%s/%s" % (m.get("provider"), m.get("model")) for m in events.get("actual_models", [])) or "无",
            yes_no(events.get("model_match")),
            ",".join(events.get("provider_thinking_levels", [])) or "未回报（只能确认请求的级别；映射方式取决于协议）"),
        "- Pi 退出码：%s · 用时 %ss / 上限 %ss · 超时：%s · 取消：%s · 残留进程：%s" % (
            run.get("exit_code"), run.get("wall_seconds"), run.get("timeout_seconds"),
            yes_no(run.get("timed_out")), yes_no(run.get("interrupted")), run.get("stray_processes")),
        "- 事件流：完整=%s（%s）· 行数 %s · 最终 stopReason=%s · 工具错误 %s · 自动重试 %s · 压缩 %s" % (
            yes_no(events.get("complete")), events.get("terminal_event"), events.get("lines"),
            events.get("final_stop_reason"), events.get("tool_errors"), len(events.get("auto_retries", [])),
            events.get("compactions")),
        "- 用量：input %s / output %s / cacheRead %s / cacheWrite %s · 费用 %s（%s）" % (
            usage.get("input"), usage.get("output"), usage.get("cacheRead"), usage.get("cacheWrite"),
            "未知" if cost.get("total") is None else cost.get("total"), cost.get("status")),
        "- 执行报告：%s（执行器自述状态：%s）" % (report.get("status"), report.get("executor_status")),
        "- 变更：%s · 越界 %d · 警告 %d" % (
            " ".join("%s%s" % (k, v) for k, v in scope.get("counts", {}).items()),
            len(scope.get("violations", [])), len(scope.get("warnings", []))),
        "",
    ]
    if events.get("problems"):
        lines += ["## 执行完整性问题", ""] + ["- %s" % p for p in events["problems"]] + [""]
    if scope.get("files"):
        lines += ["## 变更文件", "", "| 状态 | 路径 | 范围 |", "|---|---|---|"]
        lines += ["| %s | `%s` | %s |" % (f["status"], f["path"], f["scope"]) for f in scope["files"]]
        lines.append("")
    if scope.get("violations") or scope.get("warnings"):
        lines += ["## 越界与警告", ""]
        lines += ["- 越界 `%s`：%s（%s）" % (v["path"], v["kind"], v["detail"]) for v in scope.get("violations", [])]
        lines += ["- 警告 `%s`：%s（%s）" % (w["path"], w["kind"], w["detail"]) for w in scope.get("warnings", [])]
        lines.append("")
    attention: List[str] = []
    for item in events.get("suspicious_commands", []):
        if item.get("match"):
            attention.append("可疑命令（%s）：命令第 %s / %s 行 `%s`（事件流第 %s 行）"
                             % (item["label"], item["match_line"], item["command_lines"],
                                item["match"].replace("`", "'"), item["event_line"]))
        else:
            attention.append("可疑命令（%s）：`%s`" % (item["label"], item["command"].replace("`", "'")))
    temp_uses = events.get("temp_path_uses", [])
    if temp_uses:
        total_temp_uses = events.get("temp_path_use_count", len(temp_uses))
        attention.append("系统临时路径线索（%d 个命中片段）：逐项按 AGENTS.md 核对写法、用途和工具结果。"
                         "这些是事后扫描线索，不是命令阻断或违规裁定；清理输出或路径当前不存在，不能证明此前未覆盖既有内容"
                         % total_temp_uses)
        for item in temp_uses:
            attention.append("临时路径：事件流第 %s 行，命令第 %s 行 `%s`"
                             % (item["event_line"], item["match_line"], item["match"].replace("`", "'")))
        if total_temp_uses > len(temp_uses):
            attention.append("临时路径摘录已截断：另有 %d 个命中片段未展示，须继续核对 events.jsonl 原始命令；"
                             "events-summary.json 仅保留前 %d 条摘录"
                             % (total_temp_uses - len(temp_uses), len(temp_uses)))
    notes: List[str] = []
    caches = events.get("cache_dir_cleanups", [])
    if caches:
        notes.append("执行器删除了工作副本内的缓存目录（__pycache__ 等，%d 处，例如事件流第 %s 行 `%s`），"
                     "不列为可疑命令" % (len(caches), caches[0]["event_line"],
                                     caches[0]["command"].replace("`", "'")))
    for item in events.get("outside_worktree_paths", []):
        detail = [item["tool"]]
        if item.get("failed") is True:
            detail.append("调用失败")
        elif item.get("failed") is False:
            detail.append("调用成功")
        if item.get("exists") is False:
            detail.append("路径不存在，可能是手写绝对路径时拼错")
        attention.append("工作副本外路径（%s）：`%s`" % ("，".join(detail), item["path"]))
    own_reads = sorted({item["path"] for item in events.get("own_run_paths", [])})
    if own_reads:
        notes.append("执行器访问了本 attempt 运行目录中的文件（合同与执行说明）：%s"
                     % "、".join("`%s`" % p for p in own_reads[:5]))
    for path in extra.get("new_ignored_paths", []):
        attention.append("新增被 Git 忽略的路径：`%s`" % path)
    changes = extra.get("main_repo_changes") or {}
    if changes.get("head_changed"):
        attention.append("运行期间主工作区 HEAD 由 `%s` 变为 `%s`：可能是规划器在批次运行期间集成了其他候选，"
                         "也可能是越界提交" % ((changes.get("head_before") or "?")[:12],
                                          (changes.get("head_after") or "?")[:12]))
    if changes.get("other_paths"):
        attention.append("运行期间主工作区以下文件发生变化（不在规划路径内，需确认不是执行器写入）：%s"
                         % "、".join("`%s`" % p for p in changes["other_paths"][:10]))
    if changes.get("planner_paths"):
        notes.append("运行期间规划路径有变化（通常是规划器自己编辑合同或复审记录）：%s"
                     % "、".join("`%s`" % p for p in changes["planner_paths"][:10]))
    if extra.get("main_repo_changed") and (changes.get("diff_error") or not changes):
        attention.append("运行期间主工作区的 HEAD 或状态发生变化（可能是并发编辑，也可能是越界写入）；%s"
                         % (changes.get("diff_error") or "未能列出变化的路径"))
    hints = extra.get("review_hints", {})
    for marker in hints.get("skip_markers_added", []):
        attention.append("新增跳过/聚焦标记：`%s`" % marker.replace("`", "'"))
    if hints.get("assertion_lines_removed"):
        attention.append("删除了 %s 行含断言的代码（新增 %s 行）" % (
            hints["assertion_lines_removed"], hints.get("assertion_lines_added")))
    for flag in events.get("stderr_flags", []):
        attention.append("stderr 标记：%s" % flag)
    conflicts = report.get("contract_conflicts") or 0
    declared = conflicts + (report.get("unresolved_questions") or 0)
    if conflicts:
        attention.append("执行器报告了 %d 处合同矛盾或含义不明（executor-report.json 的 contract_conflicts）："
                         "逐条裁定后再下结论；相关实现是执行器的临时选择" % conflicts)
    mention_count = events.get("ambiguity_mention_count") or 0
    if mention_count:
        first = (events.get("ambiguity_mentions") or [{}])[0]
        text = "执行过程中有 %d 处提到合同的歧义、矛盾或一致性，可能只是在检查，需要核实（例如事件流第 %s 行：“%s”）" % (
            mention_count, first.get("line"), str(first.get("excerpt", "")).replace("`", "'")[:160])
        if declared:
            notes.append(text + "；报告列出了 contract_conflicts / unresolved_questions，核对两者是否一致")
        else:
            attention.append(text + "；报告的 contract_conflicts 与 unresolved_questions 都为空：核对执行器是否"
                             "自行选定了某种解释（全部摘录见 events-summary.json 的 ambiguity_mentions）")
    if attention:
        lines += ["## 复审需要关注", ""] + ["- %s" % a for a in attention] + [""]
    if notes:
        lines += ["## 备注", ""] + ["- %s" % n for n in notes] + [""]
    rel = display_path(run_dir, repo.root)
    lines += ["## 下一步", "", "```bash",
              "bash scripts/dispatch-pi.sh check %s" % rel,
              "```", "",
              "证据文件：events.jsonl、stderr.log、run.json、events-summary.json、candidate.patch、scope.json、executor-report.md。",
              "进程退出码为 0 不代表任务通过；结论以独立检查与复审为准。", ""]
    write_text(run_dir / "summary.md", "\n".join(lines), exclusive=False)


# ---------------------------------------------------------------------------
# 子命令
# ---------------------------------------------------------------------------

def _print_messages(errors: Sequence[str], warnings: Sequence[str]) -> None:
    for warning in warnings:
        # 以 NOTE： 开头的是只需知道、不需处理的提示（例如 base_sha 只落后合同提交），不冒充 WARN
        if warning.startswith(NOTE_PREFIX):
            print("NOTE  %s" % warning[len(NOTE_PREFIX):])
        else:
            print("WARN  %s" % warning)
    for error in errors:
        print("ERROR %s" % error)


def cmd_validate(args: argparse.Namespace) -> int:
    repo = Repo.discover(args.repo)
    args.plan_key = plan_key_from_arg(repo, args.plan_key)
    contract, errors, warnings = validate_plan(repo, args.plan_key)
    _print_messages(errors, warnings)
    if errors:
        print("合同无效：%d 个错误，%d 个警告。" % (len(errors), len(warnings)))
        return EXIT_USAGE
    print("合同有效：%s（%d 个警告）。" % (args.plan_key, len(warnings)))
    return EXIT_OK


def cmd_derive_json(args: argparse.Namespace) -> int:
    """由 .agent/plans/<plan-key>.md 生成同名 .json，然后立即校验两者是否一致。"""
    repo = Repo.discover(args.repo)
    key = plan_key_from_arg(repo, args.plan_key)
    md_path, json_path = repo.plan_paths(key)
    if not md_path.is_file():
        raise DispatchError("缺少文件：%s" % display_path(md_path, repo.root), EXIT_USAGE)
    contract, problems = derive_contract_json(md_path.read_text(encoding="utf-8"), args.title)
    for problem in problems:
        print("WARN  %s" % problem)
    derived_title = contract.get("title") or ""
    if not args.title and len(derived_title) > LONG_TITLE_CHARS:
        print("NOTE  标题取自 Goal 第一行（%d 字），会成为分支提交的主题行，也显示在 status 与指标里；"
              "较长时用 --title 指定一句短标题（加 --force 覆盖已生成的 JSON）" % len(derived_title))
    text = json.dumps(contract, ensure_ascii=False, indent=2) + "\n"
    if args.print_only:
        print(text, end="")
        return EXIT_OK if not problems else EXIT_USAGE
    if json_path.exists() and not args.force:
        raise DispatchError("%s 已存在；确认要覆盖时加 --force" % display_path(json_path, repo.root), EXIT_USAGE)
    json_path.write_text(text, encoding="utf-8")
    print("已写入 %s" % display_path(json_path, repo.root))
    _contract, errors, warnings = validate_plan(repo, key)
    _print_messages(errors, warnings)
    if errors:
        print("合同无效：%d 个错误，%d 个警告。" % (len(errors), len(warnings)))
        return EXIT_USAGE
    print("合同有效：%s（%d 个警告）。" % (key, len(warnings)))
    return EXIT_USAGE if problems else EXIT_OK


def _run_setup(run_dir: Path, work_dir: Path, contract: Dict[str, Any], config: Dict[str, Any]) -> List[Dict[str, Any]]:
    results = []
    if not contract["setup"]:
        return results
    setup_dir = run_dir / "setup"
    setup_dir.mkdir()
    env, _removed = child_env(config)
    for item in contract["setup"]:
        results.append(_run_command_item(item, work_dir, env, setup_dir, float(config.get("kill_grace_seconds", 15))))
        if not results[-1]["passed"]:
            break
    return results


def _resolve_argv(argv: List[str], cwd: Path, env: Dict[str, str]) -> List[str]:
    program = argv[0]
    if "/" in program or "\\" in program:
        candidate = (cwd / program) if not os.path.isabs(program) else Path(program)
        return [str(candidate)] + argv[1:]
    found = shutil.which(program, path=env.get("PATH") or env.get("Path"))
    return [found or program] + argv[1:]


def _run_command_item(item: Dict[str, Any], work_dir: Path, env: Dict[str, str], out_dir: Path,
                      grace: float) -> Dict[str, Any]:
    cid = item["id"]
    cwd = (work_dir / item.get("cwd", ".")).resolve()
    record: Dict[str, Any] = {"id": cid, "argv": item["argv"], "cwd": item.get("cwd", "."),
                              "required": item.get("required", True),
                              "expected_exit_code": item.get("expected_exit_code", 0),
                              "log": "%s/%s.log" % (out_dir.name, cid), "started_at": utc_now()}
    if not is_within(cwd, work_dir) or not cwd.is_dir():
        record.update(status="blocked", passed=False, reason="cwd 不存在或位于工作副本之外")
        return record
    run_env = dict(env)
    run_env.setdefault("CI", "1")
    run_env.update(item.get("env", {}))
    argv = _resolve_argv(list(item["argv"]), cwd, run_env)
    try:
        ensure_argv_safe(argv)
    except DispatchError as exc:
        record.update(status="blocked", passed=False, reason=str(exc))
        return record
    log_path = out_dir / ("%s.log" % cid)
    with open(log_path, "xb") as handle:
        result = run_supervised(argv, cwd, run_env, handle, subprocess.STDOUT, item["timeout_seconds"], grace)
    text = log_path.read_text(encoding="utf-8", errors="replace")
    must = [{"pattern": p, "matched": bool(re.search(p, text, re.M))} for p in item.get("output_must_match", [])]
    must_not = [{"pattern": p, "matched": bool(re.search(p, text, re.M))}
                for p in item.get("output_must_not_match", [])]
    record.update(result)
    record.update({"ended_at": utc_now(), "log_sha256": sha256_file(log_path), "log_bytes": log_path.stat().st_size,
                   "output_must_match": must, "output_must_not_match": must_not, "resolved_argv0": argv[0]})
    if result["spawn_error"]:
        record.update(status="blocked", passed=False, reason=result["spawn_error"])
    elif result["timed_out"] or result["interrupted"]:
        record.update(status="failed", passed=False, reason="超时" if result["timed_out"] else "被取消")
    else:
        ok = result["exit_code"] == record["expected_exit_code"] and all(m["matched"] for m in must) \
            and not any(m["matched"] for m in must_not)
        reasons = []
        if result["exit_code"] != record["expected_exit_code"]:
            reasons.append("退出码 %s ≠ 期望 %s" % (result["exit_code"], record["expected_exit_code"]))
        reasons += ["输出未匹配 %s" % m["pattern"] for m in must if not m["matched"]]
        reasons += ["输出命中禁止模式 %s" % m["pattern"] for m in must_not if m["matched"]]
        record.update(status="passed" if ok else "failed", passed=ok, reason="; ".join(reasons))
    return record


#: 候选仍可能被集成的 attempt 状态：它们的改动范围与新 attempt 重叠时，集成顺序需要人来安排。
PENDING_INTEGRATION_STATES = ("PREPARING", "PREPARED", "RUNNING", "COLLECTING", "NEEDS_REVIEW",
                              "PASS", "ACCEPTED_WITH_EXCEPTION", "REVISE")


def _scope_files(contract: Dict[str, Any]) -> set:
    scope = contract.get("scope") if isinstance(contract.get("scope"), dict) else {}
    files: set = set()
    for key in ("allowed_modified_files", "allowed_new_files", "allowed_deleted_files"):
        values = scope.get(key, [])
        if isinstance(values, list):
            files.update(v for v in values if isinstance(v, str))
    return files


def pending_attempt_notes(repo: Repo, contract: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """并行派遣的提示：返回（警告, 提示）。

    警告：其他任务里尚未集成的 attempt 与本合同的改动范围重叠——同一基线上并行修改同一文件，
    后集成的一方需要合并或返工。每个任务只看最新的 attempt：返工（REVISE）之后的新 attempt
    代表这个任务的现状，旧 attempt 的候选已经并入返工基线；最新 attempt 已集成或放弃时不再提示。
    提示：正在运行的 attempt 数量——它们结束前改动主工作区（合并、提交或编辑规划路径之外的
    文件）会出现在它们的复审提示中。
    """
    mine = _scope_files(contract)
    warnings: List[str] = []
    running: List[str] = []
    tasks = sorted(d.name for d in repo.runs_dir.iterdir() if d.is_dir()) if repo.runs_dir.is_dir() else []
    for task in tasks:
        attempts = task_attempts(repo, task)
        for attempt in attempts:
            if get_state(attempt) == "RUNNING":
                running.append(display_path(attempt, repo.runs_dir))
        if task == contract.get("task_id") or not attempts:
            continue
        latest = attempts[-1]
        state = get_state(latest)
        if state not in PENDING_INTEGRATION_STATES:
            continue
        other = read_json_or(latest / "contract.json", {})
        overlap = sorted(mine & _scope_files(other if isinstance(other, dict) else {}))
        if overlap:
            warnings.append("与未集成的 %s（%s）改动范围重叠：%s；并行派遣时后集成的一方需要合并或返工"
                            % (display_path(latest, repo.runs_dir), state, "、".join(overlap[:10])))
    notes = []
    if running:
        notes.append("有 %d 个 attempt 正在运行（%s）：它们结束前不要合并、提交或改动规划路径之外的主工作区文件"
                     % (len(running), "、".join(running[:5])))
    return warnings, notes


def cmd_prepare(args: argparse.Namespace) -> int:
    repo = Repo.discover(args.repo)
    args.plan_key = plan_key_from_arg(repo, args.plan_key)
    contract, errors, warnings = validate_plan(repo, args.plan_key)
    if contract is not None:
        overlap_warnings, running_notes = pending_attempt_notes(repo, contract)
        warnings = list(warnings) + overlap_warnings
        for note in running_notes:
            print("NOTE  %s" % note)
    _print_messages(errors, warnings)
    if errors or contract is None:
        raise DispatchError("合同校验失败，未创建 attempt。", EXIT_USAGE)
    if git(["check-ignore", "-q", ".agent/runs/probe"], repo.root, check=False).returncode != 0:
        raise DispatchError("请先把 .agent/runs/ 加入 .gitignore：运行证据含源码与日志，不应进入提交。", EXIT_BLOCKED)
    config = repo.config()
    md_path, json_path = repo.plan_paths(args.plan_key)
    raw_executor = read_json(json_path).get("executor", {})
    if raw_executor.get("provider") and raw_executor.get("model"):
        resolve_executor(dict(contract, _raw_executor=raw_executor), config)
    task_id, version, base = contract["task_id"], contract["plan_version"], contract["base_sha"]
    budget = contract["budget"]
    usage = budget_usage(repo, task_id)
    if usage["attempts_started"] >= budget["max_attempts_total"]:
        raise DispatchError("BUDGET_EXCEEDED：任务 %s 已运行 %d 次，达到 max_attempts_total=%d。"
                            % (task_id, usage["attempts_started"], budget["max_attempts_total"]))
    if usage["wall_seconds_used"] >= budget["max_wall_seconds_total"]:
        raise DispatchError("BUDGET_EXCEEDED：累计运行 %.0fs，达到 max_wall_seconds_total=%d。"
                            % (usage["wall_seconds_used"], budget["max_wall_seconds_total"]))
    worktree_root = repo.worktree_root(config)
    worktree_root.mkdir(parents=True, exist_ok=True)
    run_dir, number = allocate_attempt(repo, task_id)
    attempt_id = "%s.v%d.a%03d" % (task_id, version, number)
    try:
        shutil.copyfile(str(md_path), str(run_dir / "plan.md"))
        shutil.copyfile(str(json_path), str(run_dir / "contract.json"))
        # 唯一的空目录：不复用、不删除来历不明的旧目录（git 允许在空目录上建立 worktree）。
        worktree = Path(tempfile.mkdtemp(prefix="%s-%s-a%03d-" % (repo.root.name[:16], task_id[:24], number),
                                         dir=str(worktree_root))).resolve()
        source_status = git(["status", "--porcelain=v1", "-z"], repo.root).stdout
        (run_dir / "source-status.z").write_bytes(source_status)
        meta = {
            "tool_version": TOOL_VERSION, "task_id": task_id, "plan_version": version, "plan_key": args.plan_key,
            "attempt_no": number, "attempt_id": attempt_id, "repository": str(repo.root), "base_sha": base,
            "worktree": str(worktree), "plan_md_sha256": sha256_file(run_dir / "plan.md"),
            "contract_json_sha256": sha256_file(run_dir / "contract.json"), "risk_level": contract["risk_level"],
            "source_worktree_dirty": bool(source_status), "created_at": utc_now(),
            "platform": platform.platform(), "python": platform.python_version(),
            # 行尾归一化配置：之后所有快照与补丁重建都沿用它，不受运行期间全局配置变化影响
            "git_autocrlf": effective_autocrlf(repo.root),
        }
        write_json(run_dir / "meta.json", meta, exclusive=True)
        set_state(run_dir, "PREPARING")
        git(["worktree", "add", "--detach", str(worktree), base], repo.root)
        setup = _run_setup(run_dir, worktree, contract, config)
        if setup:
            write_json(run_dir / "setup.json", setup, exclusive=True)
        failed = [s for s in setup if not s["passed"]]
        dirty = "" if failed else git(["status", "--porcelain=v1"], worktree).stdout.decode("utf-8", "replace").strip()
    except BaseException as exc:
        set_state(run_dir, "PREPARE_FAILED", reason="%s: %s" % (type(exc).__name__, exc))
        if isinstance(exc, (DispatchError, OSError)):
            raise DispatchError("prepare 失败（%s 已标记 PREPARE_FAILED）：%s" % (attempt_id, exc))
        raise
    if failed:
        set_state(run_dir, "PREPARE_FAILED", reason="setup %s 失败：%s" % (failed[0]["id"], failed[0].get("reason")))
        print("setup 失败：%s（日志 %s）。修正后重新 prepare；本 attempt 未领取，不计入尝试次数。"
              % (failed[0]["id"], display_path(run_dir / failed[0]["log"], repo.root)))
        return EXIT_FAIL
    if dirty:
        set_state(run_dir, "PREPARE_FAILED", reason="setup 后 worktree 有未忽略的变更")
        print("setup 修改了受版本管理的文件或产生了未忽略的新文件：\n%s" % dirty[:2000])
        return EXIT_FAIL
    set_state(run_dir, "PREPARED")
    print("PREPARED %s" % attempt_id)
    print("Run directory: %s" % run_dir)
    print("Worktree: %s" % worktree)
    if not contract["setup"]:
        print("合同没有 setup。测试需要额外依赖时，按 dispatch-pi 技能出新版本合同补上 setup，再重新 prepare；"
              "不要在 worktree 里手工准备，否则 check --fresh 无法复现。")
    print("下一步（在后台运行）：bash scripts/dispatch-pi.sh run %s" % display_path(run_dir, repo.root))
    return EXIT_OK


def _expects_settled(version_text: str) -> Optional[bool]:
    version = parse_version(version_text or "")
    return None if version is None else version >= MIN_PI_VERSION


def cmd_run(args: argparse.Namespace) -> int:
    repo = Repo.discover(args.repo)
    run_dir = resolve_run_dir(repo, args.run_dir)
    meta, contract = load_attempt(repo, run_dir)
    state = get_state(run_dir)
    if state != "PREPARED" or (run_dir / "claim").exists():
        raise DispatchError("attempt 状态为 %s%s，只能运行未领取的 PREPARED attempt；返工请重新 prepare。"
                            % (state, "（已领取）" if (run_dir / "claim").exists() else ""))
    problems = verify_inputs(run_dir, meta)
    work_dir = Path(meta["worktree"])
    if not work_dir.is_dir():
        problems.append("worktree 不存在：%s" % work_dir)
    else:
        if git_text(["rev-parse", "HEAD"], work_dir) != meta["base_sha"]:
            problems.append("worktree HEAD 已不是基线提交")
        if git(["status", "--porcelain=v1"], work_dir).stdout.strip():
            problems.append("worktree 在运行前已有未忽略的变更")
    if problems:
        log_event(run_dir, "run_refused", problems=problems)
        raise DispatchError("输入不一致（G0）：%s" % "；".join(problems))
    config = repo.config()
    executor = resolve_executor(dict(contract, _raw_executor=load_raw_executor(run_dir)), config)
    budget = contract["budget"]
    usage = budget_usage(repo, meta["task_id"], exclude=run_dir)
    if usage["attempts_started"] >= budget["max_attempts_total"]:
        raise DispatchError("BUDGET_EXCEEDED：已达到 max_attempts_total=%d。" % budget["max_attempts_total"])
    env, removed = child_env(config)
    pi_cmd = resolve_pi_command()
    preflight = pi_preflight(pi_cmd, work_dir, executor, run_dir / "preflight", env)
    context = context_evidence(work_dir, executor["context_files"])
    write_json(run_dir / "preflight" / "context-files.json", context)
    if not preflight["ok"]:
        log_event(run_dir, "preflight_failed", problems=preflight["problems"])
        for problem in preflight["problems"]:
            print("PREFLIGHT %s" % problem)
        raise DispatchError("预检失败：attempt 保持 PREPARED，未计入尝试次数。修正环境后可再次 run。")
    for note in preflight["notes"] + context["warnings"]:
        print("NOTE  %s" % note)
    expects_settled = _expects_settled(preflight.get("pi_version", ""))
    # 领取之前完成所有可能失败、又不需要领取的准备，避免留下“已领取却无法运行”的 attempt。
    cmd = list(pi_cmd) + ["--provider", executor["provider"], "--model", executor["model"],
                          "--thinking", executor["thinking"], "--no-session"] + RESOURCE_FLAGS
    if executor["context_files"] == "none":
        cmd.append("--no-context-files")
    cmd += ["--tools", ",".join(executor["tools"]), "--mode", "json",
            "@" + str(run_dir / "plan.md"), "@" + str(run_dir / "instruction.md")]
    ensure_argv_safe(cmd)
    ignored_before = ignored_inventory(work_dir)
    main_before = main_repo_fingerprint(repo.root, run_dir)
    # 临界区：在 task 级锁内重新核算预算、预留本轮时长并领取。
    with TaskLock(repo, meta["task_id"]):
        usage = budget_usage(repo, meta["task_id"], exclude=run_dir)
        if usage["attempts_started"] >= budget["max_attempts_total"]:
            raise DispatchError("BUDGET_EXCEEDED：已达到 max_attempts_total=%d。" % budget["max_attempts_total"])
        remaining_total = budget["max_wall_seconds_total"] - usage["wall_seconds_used"]
        if remaining_total < 60:
            raise DispatchError("BUDGET_EXCEEDED：剩余墙钟预算 %.0fs，不足 60s。" % remaining_total)
        timeout = int(min(budget["max_wall_seconds_per_attempt"], remaining_total))
        if args.timeout:
            timeout = max(1, min(timeout, args.timeout))
        try:
            (run_dir / "claim").mkdir()
        except FileExistsError:
            raise DispatchError("该 attempt 已被领取，不能重复运行。")
        write_json(run_dir / "claim" / "reservation.json",
                   {"timeout_seconds": timeout, "pid": os.getpid(), "at": utc_now()}, exclusive=True)
    run_info: Dict[str, Any] = {"command": cmd, "cwd": str(work_dir), "timeout_seconds": timeout,
                                "env_removed": removed, "started_at": utc_now(), "main_repo_before": main_before,
                                "expects_agent_settled": expects_settled}
    try:
        write_json(run_dir / "executor.json", executor, exclusive=True)
        write_text(run_dir / "instruction.md", render_instruction(meta, contract, executor, timeout,
                                                                  extra_protected_paths(config),
                                                                  read_json_or(run_dir / "setup.json", [])))
        write_json(run_dir / "ignored-before.json", ignored_before, exclusive=True)
        write_json(run_dir / "run-started.json", run_info, exclusive=True)
        set_state(run_dir, "RUNNING")
    except BaseException as exc:
        run_info.update(spawn_error="领取后、启动前失败：%s: %s" % (type(exc).__name__, exc), exit_code=None,
                        wall_seconds=0.0, ended_at=utc_now())
        write_json(run_dir / "run.json", run_info)
        set_state(run_dir, "INFRA_FAILURE", reason=run_info["spawn_error"])
        raise
    print("RUNNING %s（时限 %ss）" % (meta["attempt_id"], timeout), flush=True)
    grace = float(config.get("kill_grace_seconds", 15))

    def record_pid(pid: int) -> None:
        write_text(run_dir / "pid.txt", "%d\n" % pid)

    with open(run_dir / "events.jsonl", "xb") as out, open(run_dir / "stderr.log", "xb") as err:
        result = run_supervised(cmd, work_dir, env, out, err, timeout, grace, on_spawn=record_pid)
    run_info.update(result)
    run_info["ended_at"] = utc_now()
    write_json(run_dir / "run.json", run_info, exclusive=True)
    set_state(run_dir, "COLLECTING")
    final_state = collect(repo, run_dir, meta, contract, executor, run_info)
    print("%s %s" % (final_state, meta["attempt_id"]))
    print("Summary: %s" % (run_dir / "summary.md"))
    events = read_json_or(run_dir / "events-summary.json", {})
    return EXIT_OK if final_state == "NEEDS_REVIEW" and events.get("ok") else EXIT_FAIL


def collect(repo: Repo, run_dir: Path, meta: Dict[str, Any], contract: Dict[str, Any], executor: Dict[str, Any],
            run_info: Dict[str, Any]) -> str:
    work_dir = Path(meta["worktree"])
    base = meta["base_sha"]
    events, final_text = summarize_events(run_dir / "events.jsonl", work_dir, executor, run_dir / "stderr.log",
                                          expects_settled=run_info.get("expects_agent_settled"),
                                          allowed_outside=[run_dir],
                                          plan_text=read_text_or(run_dir / "plan.md"))
    write_json(run_dir / "events-summary.json", events)
    write_json(run_dir / "report-status.json", extract_report(final_text, run_dir))
    candidate: Dict[str, Any] = {}
    collect_errors: List[str] = []
    try:
        candidate = record_candidate(repo, run_dir, work_dir, base)
        write_json(run_dir / "candidate.json", candidate, exclusive=True)
        head_after = git_text(["rev-parse", "HEAD"], work_dir)
        changes = diff_raw(work_dir, base, candidate["tree"])
        write_json(run_dir / "changes.json", changes, exclusive=True)
        scope = evaluate_scope(changes, contract, head_after, base, extra_protected_paths(repo.config()))
        scope["head_after"] = head_after
        write_json(run_dir / "scope.json", scope, exclusive=True)
    except (DispatchError, OSError) as exc:
        collect_errors.append(str(exc))
    observations: Dict[str, Any] = {"collect_errors": collect_errors}
    try:
        before = read_json_or(run_dir / "ignored-before.json", [])
        after = ignored_inventory(work_dir)
        observations["new_ignored_paths"] = sorted(set(after) - set(before))[:200]
    except DispatchError as exc:
        observations["new_ignored_paths_error"] = str(exc)
    main_after = main_repo_fingerprint(repo.root, run_dir)
    main_before = run_info.get("main_repo_before") or {}
    observations["main_repo_after"] = main_after
    observations["main_repo_changed"] = bool(main_before) and main_before != main_after
    observations["main_repo_coverage"] = "HEAD 与已跟踪、未被忽略文件的内容；不含被忽略的文件与仓库之外的路径"
    try:
        observations["main_repo_changes"] = main_repo_changes(repo.root, main_before, main_after,
                                                              planner_paths(repo.config()))
    except DispatchError as exc:
        observations["main_repo_changes"] = {"changed": observations["main_repo_changed"], "diff_error": str(exc)}
    if candidate.get("tree") and (run_dir / "candidate.patch").exists():
        observations["review_hints"] = review_hints(run_dir / "candidate.patch")
    write_json(run_dir / "observations.json", observations)
    if run_info.get("spawn_error") or collect_errors or not candidate.get("tree"):
        state = "INFRA_FAILURE"
    elif run_info.get("timed_out"):
        state = "TIMEOUT"
    elif run_info.get("interrupted"):
        state = "CANCELLED"
    elif not events.get("assistant_messages"):
        state = "INFRA_FAILURE"  # 模型从未产生回复：启动、凭据或模型配置问题
    else:
        state = "NEEDS_REVIEW"
    set_state(run_dir, state, exit_code=run_info.get("exit_code"), events_ok=events.get("ok"),
              scope_ok=read_json_or(run_dir / "scope.json", {}).get("ok"))
    write_summary(run_dir, repo)
    return state


def cmd_collect(args: argparse.Namespace) -> int:
    repo = Repo.discover(args.repo)
    run_dir = resolve_run_dir(repo, args.run_dir)
    meta, contract = load_attempt(repo, run_dir)
    state = get_state(run_dir)
    claimed = (run_dir / "claim").is_dir()
    recoverable = state in ("RUNNING", "COLLECTING") or (state == "PREPARED" and claimed)
    if not recoverable or not args.recover:
        raise DispatchError("collect 只用于调度器异常退出后的恢复：需要状态 RUNNING/COLLECTING（或已领取的 PREPARED）"
                            "且指定 --recover（当前 %s）。" % state, EXIT_USAGE)
    started = read_json_or(run_dir / "run-started.json", {})
    pid_text = (run_dir / "pid.txt").read_text(encoding="utf-8").strip() if (run_dir / "pid.txt").exists() else ""
    pid = int(pid_text) if pid_text.isdigit() else None
    if pid_alive(pid):
        raise DispatchError("记录的 Pi 进程 %s 可能仍在运行；确认终止后再恢复。" % pid)
    run_info = read_json_or(run_dir / "run.json", None)
    if run_info is None:
        version_file = run_dir / "preflight" / "pi-version.txt"
        version_text = version_file.read_text(encoding="utf-8") if version_file.exists() else ""
        run_info = dict(started, exit_code=None, timed_out=False, interrupted=True, recovered=True,
                        ended_at=utc_now(), wall_seconds=None,
                        spawn_error=None if started else "领取后调度器退出，未启动 Pi",
                        expects_agent_settled=started.get("expects_agent_settled", _expects_settled(version_text)))
        write_json(run_dir / "run.json", run_info, exclusive=True)
    executor = read_json_or(run_dir / "executor.json", contract["executor"])
    for name in ("candidate.json", "changes.json", "scope.json", "candidate.patch"):
        path = run_dir / name
        if path.exists():
            path.rename(run_dir / (name + ".partial"))
    state = collect(repo, run_dir, meta, contract, executor, run_info)
    log_event(run_dir, "recovered_collection")
    print("%s（恢复收集；事件可能不完整）" % state)
    return EXIT_OK


def _latest_numbered(directory: Path) -> Optional[Path]:
    if not directory.is_dir():
        return None
    numbered = [d for d in directory.iterdir() if re.match(r"^\d{2,}(\.json|\.md)?$", d.name)]
    return max(numbered, key=lambda d: int(re.match(r"^(\d+)", d.name).group(1))) if numbered else None  # type: ignore


def _next_number(directory: Path) -> int:
    latest = _latest_numbered(directory)
    return int(re.match(r"^(\d+)", latest.name).group(1)) + 1 if latest else 1  # type: ignore[union-attr]


DEFAULT_ARTIFACT_PATTERNS = ("**/__pycache__/**", "**/*.pyc", "**/.pytest_cache/**", "**/.mypy_cache/**",
                             "**/.ruff_cache/**")


def artifact_matchers(config: Dict[str, Any]) -> List["re.Pattern[str]"]:
    """检查可以产生、且不视为候选漂移的缓存类文件。默认只含 Python 缓存，其余由配置显式追加。"""
    extra = [p for p in config.get("check_artifact_patterns", []) if isinstance(p, str) and not pattern_error(p)]
    return compile_patterns(list(DEFAULT_ARTIFACT_PATTERNS) + extra)


def split_extras(paths: Sequence[str], artifacts: Sequence["re.Pattern[str]"]) -> Tuple[List[str], List[str]]:
    allowed = [p for p in paths if matches(artifacts, p)]
    unexpected = [p for p in paths if not matches(artifacts, p)]
    return allowed, unexpected


def candidate_patch_ok(run_dir: Path, candidate: Dict[str, Any]) -> bool:
    patch = run_dir / "candidate.patch"
    return bool(candidate.get("patch_roundtrip_verified")) and patch.is_file() \
        and sha256_file(patch) == candidate.get("patch_sha256")


def prepare_fresh_workspace(repo: Repo, run_dir: Path, meta: Dict[str, Any], contract: Dict[str, Any],
                            candidate: Dict[str, Any], config: Dict[str, Any], out_dir: Path,
                            env: Dict[str, str], grace: float) -> Path:
    """干净的验收副本：基线 + 候选补丁 + 合同 setup，不含执行 worktree 中的任何其他文件。"""
    root = repo.worktree_root(config)
    root.mkdir(parents=True, exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix="%s-%s-a%03d-verify-" % (
        repo.root.name[:16], meta["task_id"][:24], meta["attempt_no"]), dir=str(root))).resolve()
    git(["worktree", "add", "--detach", str(workspace), meta["base_sha"]], repo.root)
    patch = run_dir / "candidate.patch"
    if patch.stat().st_size > 0:
        git(["apply", "--binary", "--whitespace=nowarn", str(patch)], workspace)
    if snapshot_tree(workspace, meta["base_sha"], out_dir, "fresh", meta.get("git_autocrlf")) != candidate["tree"]:
        raise DispatchError("干净副本与候选树不一致：%s" % workspace)
    if contract["setup"]:
        setup_dir = out_dir / "setup"
        setup_dir.mkdir()
        for item in contract["setup"]:
            record = _run_command_item(item, workspace, env, setup_dir, grace)
            if not record["passed"]:
                raise DispatchError("干净副本的 setup %s 失败：%s" % (item["id"], record.get("reason")))
        if snapshot_tree(workspace, meta["base_sha"], out_dir, "fresh-setup", meta.get("git_autocrlf")) != candidate["tree"]:
            raise DispatchError("setup 改动了干净副本中的候选文件或产生了未忽略的新文件")
    return workspace


#: 变异清单里 command 的缺省时限（秒）。
MUTATION_DEFAULT_TIMEOUT = 600


def _load_mutation_spec(path: Path) -> Tuple[Dict[str, Any], List[str]]:
    """读取并校验变异清单，返回（清单, 问题列表）。格式见 review-pi/mutation-check.md。"""
    try:
        spec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {}, ["变异清单无法读取或不是合法 JSON：%s" % exc]
    if not isinstance(spec, dict):
        return {}, ["变异清单必须是 JSON 对象"]
    problems: List[str] = []

    def relative_ok(value: Any) -> bool:
        return isinstance(value, str) and bool(value) and not os.path.isabs(value) \
            and ".." not in Path(value).parts

    command = spec.get("command")
    if not (isinstance(command, list) and command and all(isinstance(x, str) and x for x in command)):
        problems.append("command 必须是非空的字符串数组（argv，不经过 shell）")
    if not relative_ok(spec.get("cwd", ".")):
        problems.append("cwd 必须是工作副本内的相对路径")
    timeout = spec.get("timeout_seconds", MUTATION_DEFAULT_TIMEOUT)
    if not (isinstance(timeout, int) and not isinstance(timeout, bool) and timeout > 0):
        problems.append("timeout_seconds 必须是正整数")
    mutations = spec.get("mutations")
    if not (isinstance(mutations, list) and mutations):
        problems.append("mutations 必须是非空数组")
        mutations = []
    names = set()
    for index, item in enumerate(mutations, start=1):
        label = "mutations[%d]" % index
        if not isinstance(item, dict):
            problems.append("%s 必须是对象" % label)
            continue
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            problems.append("%s.name 必须是非空字符串" % label)
        elif name in names:
            problems.append("%s.name 重复：%s" % (label, name))
        else:
            names.add(name)
        if not relative_ok(item.get("file")):
            problems.append("%s.file 必须是工作副本内的相对路径" % label)
        old, new = item.get("old"), item.get("new")
        if not isinstance(old, str) or not old:
            problems.append("%s.old 必须是非空字符串" % label)
        if not isinstance(new, str):
            problems.append("%s.new 必须是字符串" % label)
        elif new == old:
            problems.append("%s.new 与 old 相同，不构成变异" % label)
        count = item.get("count", 1)
        if not (isinstance(count, int) and not isinstance(count, bool) and count >= 1):
            problems.append("%s.count 必须是正整数" % label)
    return spec, problems


def _apply_mutation(path: Path, old: str, new: str, count: int) -> Tuple[bytes, int]:
    """把文件中的 old 全部换成 new，但只在它恰好出现 count 次时才写入。

    返回（原始字节, 实际出现次数），调用方用原始字节恢复文件。清单按 LF 书写即可：
    文件是 CRLF 换行时（例如 Windows 上 autocrlf 检出的副本），先按 LF 比对，写回时
    再换回 CRLF。文件不是 UTF-8 文本时抛 UnicodeDecodeError。
    """
    original = path.read_bytes()
    text = original.decode("utf-8")
    crlf, lf = chr(13) + chr(10), chr(10)
    uses_crlf = crlf in text
    normalized = text.replace(crlf, lf) if uses_crlf else text
    found = normalized.count(old)
    if found == count:
        mutated = normalized.replace(old, new)
        if uses_crlf:
            mutated = mutated.replace(lf, crlf)
        path.write_bytes(mutated.encode("utf-8"))
    return original, found


def cmd_mutate(args: argparse.Namespace) -> int:
    """在干净副本（基线 + 候选补丁 + setup）上逐个套用最小变异，看测试能否抓住。

    先不做变异运行一次 command，必须通过；之后每个变异单独运行，command 失败（退出码
    非 0 或超时）记为“抓住”，通过记为“漏掉”，old 的出现次数与 count 不符记为“跳过”。
    每次运行后恢复原文件。记录写到 <run-dir>/mutations/NN/。
    """
    repo = Repo.discover(args.repo)
    run_dir = resolve_run_dir(repo, args.run_dir)
    meta, contract = load_attempt(repo, run_dir)
    state = get_state(run_dir)
    if state not in REVIEWABLE_STATES and state != "INTEGRATED":
        raise DispatchError("状态 %s 不能做变异检查" % state)
    candidate = read_json_or(run_dir / "candidate.json", {})
    if not candidate.get("tree") or not candidate_patch_ok(run_dir, candidate):
        raise DispatchError("候选补丁缺失、被改动或未通过往返校验，不能建立干净副本")
    spec_path = Path(args.spec)
    spec, problems = _load_mutation_spec(spec_path)
    if problems:
        for problem in problems:
            print("ERROR %s" % problem)
        raise DispatchError("变异清单无效：%d 个问题" % len(problems), EXIT_USAGE)
    config = repo.config()
    env, _removed = child_env(config)
    grace = float(config.get("kill_grace_seconds", 15))
    root = run_dir / "mutations"
    root.mkdir(exist_ok=True)
    number = _next_number(root)
    out_dir = root / ("%02d" % number)
    out_dir.mkdir()
    shutil.copyfile(str(spec_path), str(out_dir / "spec.json"))
    try:
        workspace = prepare_fresh_workspace(repo, run_dir, meta, contract, candidate, config, out_dir, env, grace)
    except (DispatchError, OSError) as exc:
        write_json(out_dir / "mutations.json", {"aborted": "fresh_workspace_failed", "error": str(exc),
                                                "at": utc_now()}, exclusive=True)
        raise DispatchError("无法建立干净副本：%s" % exc)
    base_item = {"argv": spec["command"], "cwd": spec.get("cwd", "."),
                 "timeout_seconds": spec.get("timeout_seconds", MUTATION_DEFAULT_TIMEOUT), "expected_exit_code": 0}
    results: List[Dict[str, Any]] = []
    baseline: Optional[Dict[str, Any]] = None
    drifted: List[str] = []
    started = utc_now()
    try:
        print("MUTATE baseline ...", flush=True)
        baseline = _run_command_item(dict(base_item, id="baseline"), workspace, env, out_dir, grace)
        if not baseline["passed"]:
            write_json(out_dir / "mutations.json", {"aborted": "baseline_failed", "baseline": baseline,
                                                    "at": utc_now()}, exclusive=True)
            raise DispatchError("不做变异时 command 没有通过（%s），变异结果没有意义；先让它在候选上通过"
                                % (baseline.get("reason") or baseline.get("status")))
        for index, item in enumerate(spec["mutations"], start=1):
            mid = "M%02d" % index
            count = item.get("count", 1)
            record: Dict[str, Any] = {"id": mid, "name": item["name"], "file": item["file"],
                                      "count_expected": count}
            path = workspace / item["file"]
            if not path.is_file() or not is_within(path.resolve(), workspace):
                record.update(status="skipped", reason="文件不存在或位于工作副本之外")
            else:
                try:
                    original, found = _apply_mutation(path, item["old"], item["new"], count)
                except UnicodeDecodeError:
                    record.update(status="skipped", reason="文件不是 UTF-8 文本")
                else:
                    record["count_found"] = found
                    if found != count:
                        record.update(status="skipped", reason="old 出现 %d 次，期望 %d 次" % (found, count))
                    else:
                        try:
                            run = _run_command_item(dict(base_item, id=mid), workspace, env, out_dir, grace)
                        finally:
                            path.write_bytes(original)
                        if run["status"] == "blocked":
                            status = "error"
                        else:
                            status = "missed" if run["passed"] else "caught"
                        record.update(status=status, exit_code=run.get("exit_code"),
                                      timed_out=bool(run.get("timed_out")), log=run.get("log"),
                                      reason=run.get("reason") or "")
            results.append(record)
            print("%-7s %s  %s" % (record["status"].upper(), item["name"], record.get("reason") or ""), flush=True)
        tree_after = snapshot_tree(workspace, meta["base_sha"], out_dir, "after", meta.get("git_autocrlf"))
        drifted = tree_drift(workspace, candidate["tree"], tree_after)["modified"]
    finally:
        if not args.keep_workspace:
            remove_worktree(repo, workspace)
    counts = {status: sum(1 for r in results if r["status"] == status)
              for status in ("caught", "missed", "skipped", "error")}
    payload = {"run": number, "started_at": started, "ended_at": utc_now(), "candidate_tree": candidate["tree"],
               "spec_sha256": sha256_file(out_dir / "spec.json"), "command": spec["command"],
               "cwd": spec.get("cwd", "."), "workspace": str(workspace),
               "workspace_kept": bool(args.keep_workspace), "candidate_files_left_modified": drifted,
               "baseline": baseline, "counts": counts, "results": results}
    write_json(out_dir / "mutations.json", payload, exclusive=True)
    log_event(run_dir, "mutations", run=number, **counts)
    print("变异 %d 个：抓住 %d，漏掉 %d，跳过 %d，出错 %d · %s"
          % (len(results), counts["caught"], counts["missed"], counts["skipped"], counts["error"],
             display_path(out_dir / "mutations.json", repo.root)))
    if counts["missed"]:
        print("漏掉的变异说明没有测试覆盖对应规则：合同测试清单遗漏的，由规划端补测试并单独提交；"
              "执行器少写的，记入复审（必要时 REVISE）。")
    if drifted:
        print("WARN  变异后候选文件没有恢复原样：%s（记录仍有效，干净副本%s）"
              % (", ".join(drifted[:10]), "已保留" if args.keep_workspace else "已移除"))
    return EXIT_OK


#: Codex 默认读取项目指令文件的上限（project_doc_max_bytes，字节）。
CODEX_PROJECT_DOC_MAX_BYTES = 32768
#: 技能的唯一来源（Codex 与 Pi 原生发现；执行器运行时由 --no-skills 屏蔽）。
SKILL_SOURCE_DIR = ".agents/skills"
#: Claude Code 只从这里发现技能：由 sync-adapters 从 SKILL_SOURCE_DIR 复制，不要手改。
CLAUDE_SKILL_DIR = ".claude/skills"
#: sync-adapters 负责同步的技能（只动这几个目录，不碰仓库自己的其他技能）。
KIT_SKILLS = ("check-pi-env", "plan-task", "dispatch-pi", "review-pi")


#: Windows 的 FILE_ATTRIBUTE_REPARSE_POINT：junction、符号链接等重解析点都带这个属性。
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400


def _is_link_or_junction(path: str) -> bool:
    """符号链接、Windows junction 或其他重解析点。

    Python 3.12 之前 os.path.islink 不认 junction，os.walk(followlinks=False) 也会进入 junction，
    所以在 Windows 上另外检查重解析点属性。把所有重解析点都当作链接，是保守的做法。
    """
    if os.path.islink(path):
        return True
    isjunction = getattr(os.path, "isjunction", None)  # Python 3.12+
    if isjunction is not None and isjunction(path):
        return True
    if os.name == "nt":
        try:
            attributes = getattr(os.lstat(path), "st_file_attributes", 0)
        except OSError:
            return False
        return bool(attributes & _FILE_ATTRIBUTE_REPARSE_POINT)
    return False


def _tree_files(root: Path) -> Dict[str, bytes]:
    """目录下全部普通文件的 {相对路径: 字节}。

    不跟随、也不收录符号链接与 Windows junction（见 _is_link_or_junction），跳过 __pycache__；
    目录不存在或本身是链接时为空。这样源目录中的链接不会把仓库之外的内容带进副本。
    """
    files: Dict[str, bytes] = {}
    if not root.is_dir() or _is_link_or_junction(str(root)):
        return files
    for dirpath, dirnames, filenames in os.walk(str(root), followlinks=False):
        dirnames[:] = sorted(name for name in dirnames
                             if name != "__pycache__" and not _is_link_or_junction(os.path.join(dirpath, name)))
        for filename in sorted(filenames):
            path = Path(dirpath) / filename
            if _is_link_or_junction(str(path)) or not path.is_file():
                continue
            files[path.relative_to(root).as_posix()] = path.read_bytes()
    return files


def _repo_local_path(repo_root: Path, rel: str, purpose: str) -> Path:
    """仓库相对路径 rel 的真实位置必须就是仓库内的预期位置。

    路径自身或任何上级目录是符号链接或 junction 时，解析后的位置与预期不同，抛 DispatchError。
    purpose 写进报错，说明为什么拒绝。
    """
    path = repo_root / rel
    expected = repo_root.resolve() / rel
    actual = path.resolve()
    if os.path.normcase(str(actual)) != os.path.normcase(str(expected)):
        raise DispatchError("%s 或其上级目录是符号链接或 junction（解析为 %s）：%s。先删去链接，改用真实目录"
                            % (rel, actual, purpose))
    return path


def skill_source(repo_root: Path, name: str) -> Path:
    """.agents/skills/<name> 的路径。它或上级目录是链接时拒绝读取，以免把仓库之外的内容复制进副本。"""
    return _repo_local_path(repo_root, "%s/%s" % (SKILL_SOURCE_DIR, name), "拒绝读取，以免把链接指向的内容复制进副本")


def claude_skill_target(repo_root: Path, name: str) -> Path:
    """.claude/skills/<name> 的路径，并确认它真的位于仓库内。

    它自身或上级目录（.claude、.claude/skills）是符号链接或 junction 时拒绝同步：否则删除旧副本时
    会删到链接指向的目录，可能在仓库之外，也可能正是 .agents/skills 中的源。
    """
    return _repo_local_path(repo_root, "%s/%s" % (CLAUDE_SKILL_DIR, name),
                            "拒绝同步，以免写入或删除链接指向的目录")


def claude_adapters_installed(repo_root: Path) -> bool:
    """仓库里是否装了 Claude Code 的技能副本（任一 PI-Kit 技能目录存在即算）；路径先经链接校验。"""
    return any(claude_skill_target(repo_root, name).exists() for name in KIT_SKILLS)


def adapter_drift(repo_root: Path) -> Tuple[List[str], List[str]]:
    """比较 .agents/skills 与 .claude/skills 中的 PI-Kit 技能。

    返回（源目录中缺少的技能, 副本与源不一致之处）。只比较 KIT_SKILLS，逐字节比较。源与副本都先经过
    链接校验（skill_source、claude_skill_target）：任何一侧指向仓库之外时抛 DispatchError，不读取其内容。
    """
    missing: List[str] = []
    drift: List[str] = []
    for name in KIT_SKILLS:
        source = _tree_files(skill_source(repo_root, name))
        copy_dir = claude_skill_target(repo_root, name)  # 源缺失时也先校验副本目录
        if "SKILL.md" not in source:
            missing.append(name)
            continue
        copy = _tree_files(copy_dir)
        for rel in sorted(set(source) | set(copy)):
            if rel not in copy:
                drift.append("%s/%s：副本缺失" % (name, rel))
            elif rel not in source:
                drift.append("%s/%s：副本多出（源中没有）" % (name, rel))
            elif source[rel] != copy[rel]:
                drift.append("%s/%s：内容不同" % (name, rel))
    return missing, drift


def sync_adapters(repo_root: Path) -> List[str]:
    """把 KIT_SKILLS 从 .agents/skills 整目录复制到 .claude/skills，返回实际更新的技能名。

    先校验全部目标路径（见 claude_skill_target），任何一个不安全就一个都不改。
    """
    targets = {name: claude_skill_target(repo_root, name) for name in KIT_SKILLS}
    changed: List[str] = []
    for name in KIT_SKILLS:
        source = _tree_files(skill_source(repo_root, name))
        if "SKILL.md" not in source:
            continue
        target_dir = targets[name]
        if _tree_files(target_dir) == source:
            continue
        if target_dir.exists():
            shutil.rmtree(str(target_dir))
        for rel, data in source.items():
            target = target_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        changed.append(name)
    return changed


def planner_file_notes(repo_root: Path, facts: Dict[str, Any]) -> List[str]:
    """规划端读取的规则文件与技能副本的检查（doctor 用）。"""
    notes: List[str] = []
    base = repo_root.resolve()
    agents_md = repo_root / "AGENTS.md"
    if agents_md.is_file():
        if not is_within(agents_md.resolve(), base):
            notes.append("AGENTS.md 是指向仓库之外的链接（%s）：规划端与执行器读到的是仓库之外的内容，"
                         "而且 worktree 中不一定有同样的文件" % agents_md.resolve())
        size = agents_md.stat().st_size
        facts["agents_md_bytes"] = size
        if size > CODEX_PROJECT_DOC_MAX_BYTES:
            notes.append("AGENTS.md 有 %d 字节，超过 Codex 默认读取上限 %d 字节（project_doc_max_bytes）：超出部分不会被 "
                         "Codex 读取" % (size, CODEX_PROJECT_DOC_MAX_BYTES))
    else:
        notes.append("仓库根目录没有 AGENTS.md：规划端与执行器都读不到协作规则")
    claude_md = repo_root / "CLAUDE.md"
    if claude_md.is_file():
        target = claude_md.resolve()
        if not is_within(target, base):
            # 不读取仓库之外的内容，只提示。
            notes.append("CLAUDE.md 是指向仓库之外的链接（%s）：Claude Code 会读取该文件，而不是本仓库的 AGENTS.md" % target)
        elif os.path.normcase(str(target)) == os.path.normcase(str(base / "AGENTS.md")):
            pass  # CLAUDE.md 链接到 AGENTS.md：Claude Code 文档给出的合法做法，读到的就是 AGENTS.md
        elif "@AGENTS.md" not in claude_md.read_text(encoding="utf-8", errors="replace"):
            notes.append("仓库有 CLAUDE.md，但其中没有 @AGENTS.md：有 CLAUDE.md 时 Claude Code 只读 CLAUDE.md，"
                         "读不到 AGENTS.md 中的协作规则。在 CLAUDE.md 中加一行 @AGENTS.md，或删去 CLAUDE.md")
    try:
        missing, drift = adapter_drift(repo_root)
    except DispatchError as exc:
        facts["claude_skill_adapters"] = {"error": str(exc)}
        notes.append(str(exc))
        return notes
    installed = claude_adapters_installed(repo_root)
    # 只用 Codex 时可以不装 Claude Code 副本：没有任何副本时不算不一致。
    facts["claude_skill_adapters"] = {"installed": installed, "missing_sources": missing,
                                      "drift": drift[:50] if installed else []}
    if len(missing) == len(KIT_SKILLS):
        legacy = [name for name in KIT_SKILLS if (claude_skill_target(repo_root, name) / "SKILL.md").is_file()]
        if legacy:
            notes.append("技能仍只在 .claude/skills（1.x 布局）：Codex 读不到。按 README 的升级说明移到 .agents/skills，"
                         "再运行 sync-adapters")
        else:
            notes.append("没有找到 PI-Kit 技能（.agents/skills/%s 等）" % KIT_SKILLS[0])
    elif missing:
        notes.append(".agents/skills 中缺少技能：%s" % ", ".join(missing))
    if drift and installed:
        notes.append("Claude Code 的技能副本（.claude/skills）与 .agents/skills 不一致 %d 处：运行 "
                     "bash scripts/dispatch-pi.sh sync-adapters" % len(drift))
    return notes


def cmd_sync_adapters(args: argparse.Namespace) -> int:
    """.agents/skills 是技能的唯一来源；Claude Code 只读 .claude/skills，因此复制一份给它。"""
    repo = Repo.discover(args.repo)
    missing, drift = adapter_drift(repo.root)
    if len(missing) == len(KIT_SKILLS):
        raise DispatchError("没有找到 %s/<技能>/SKILL.md：仓库可能仍是 1.x 布局（技能在 .claude/skills），"
                            "见 README 的升级说明" % SKILL_SOURCE_DIR)
    for name in missing:
        print("WARN  %s/%s 缺少 SKILL.md，跳过" % (SKILL_SOURCE_DIR, name))
    if args.check:
        for item in drift:
            print("DRIFT %s" % item)
        if drift or missing:
            print("Claude Code 的技能副本与 %s 不一致：%d 处%s。补齐源文件后运行 bash scripts/dispatch-pi.sh "
                  "sync-adapters 同步。" % (SKILL_SOURCE_DIR, len(drift),
                                           "；另有 %d 个技能缺少源文件" % len(missing) if missing else ""))
            return EXIT_FAIL
        print("Claude Code 的技能副本（%s）与 %s 一致。" % (CLAUDE_SKILL_DIR, SKILL_SOURCE_DIR))
        return EXIT_OK
    changed = sync_adapters(repo.root)
    if changed:
        print("已同步到 %s：%s。请一并提交。" % (CLAUDE_SKILL_DIR, ", ".join(changed)))
    else:
        print("Claude Code 的技能副本已是最新，没有改动。")
    if missing:
        print("缺少源文件的技能没有同步：%s" % ", ".join(missing))
        return EXIT_FAIL
    return EXIT_OK


#: wait 视为“仍在进行”的状态。
WAIT_ACTIVE_STATES = ("PREPARING", "RUNNING", "COLLECTING")


def cmd_wait(args: argparse.Namespace) -> int:
    """阻塞等待 attempt 结束，给没有后台完成通知的规划端（如 Codex）轮询用。

    进入明确的结束状态（TERMINAL_STATES）时打印状态并退出 0；到时仍在运行时打印进度并退出 3，调用方
    可以再次调用。刚在后台启动的 run 可能还没来得及领取，所以 PREPARED 状态最多再等 60 秒，仍未开始
    时退出 3。state.json 缺失、损坏或状态未知时退出 1，不把它当成已结束。
    """
    repo = Repo.discover(args.repo)
    run_dir = resolve_run_dir(repo, args.run_dir)
    if args.timeout < 1:
        raise DispatchError("--timeout 必须是正整数（秒）", EXIT_USAGE)
    started = time.monotonic()
    shown = display_path(run_dir, repo.root)
    while True:
        state = get_state(run_dir)
        elapsed = time.monotonic() - started
        if state in WAIT_ACTIVE_STATES or (state == "PREPARED" and elapsed < min(60, args.timeout)):
            if elapsed >= args.timeout:
                progress = _live_progress(run_dir) if state == "RUNNING" else ""
                print("仍在运行：%s · %s%s。再次运行 wait 继续等待。" % (shown, state, " · " + progress if progress else ""))
                return EXIT_BLOCKED
            time.sleep(max(0.2, min(args.interval, args.timeout - elapsed)))
            continue
        if state == "PREPARED":
            print("attempt 仍是 PREPARED：run 没有开始（或启动前就失败了）。检查后台命令的输出：%s" % shown)
            return EXIT_BLOCKED
        if state not in TERMINAL_STATES:
            print("无法确定 attempt 的状态（%s）：state.json 缺失、损坏或状态未知。检查 %s" % (state, shown))
            return EXIT_FAIL
        print("已结束：%s · %s" % (shown, state))
        summary = run_dir / "summary.md"
        if summary.is_file():
            print("摘要：%s" % display_path(summary, repo.root))
        return EXIT_OK


def remove_worktree(repo: Repo, path: Path) -> None:
    git(["worktree", "remove", "--force", str(path)], repo.root, check=False)


def cmd_check(args: argparse.Namespace) -> int:
    repo = Repo.discover(args.repo)
    run_dir = resolve_run_dir(repo, args.run_dir)
    meta, contract = load_attempt(repo, run_dir)
    state = get_state(run_dir)
    if state not in REVIEWABLE_STATES:
        raise DispatchError("状态 %s 不能运行验收检查" % state)
    candidate = read_json_or(run_dir / "candidate.json", {})
    if not candidate.get("tree"):
        raise DispatchError("没有候选记录（candidate.json），无法把检查绑定到确切内容")
    checks = contract["checks"]
    if args.only:
        wanted = [x.strip() for x in args.only.split(",") if x.strip()]
        unknown = [x for x in wanted if x not in {c["id"] for c in checks}]
        if unknown:
            raise DispatchError("未知检查：%s" % ", ".join(unknown), EXIT_USAGE)
        checks = [c for c in checks if c["id"] in wanted]
    if not checks:
        raise DispatchError("合同没有可运行的检查", EXIT_USAGE)
    config = repo.config()
    env, removed = child_env(config)
    grace = float(config.get("kill_grace_seconds", 15))
    artifacts = artifact_matchers(config)
    checks_root = run_dir / "checks"
    checks_root.mkdir(exist_ok=True)
    number = _next_number(checks_root)
    out_dir = checks_root / ("%02d" % number)
    out_dir.mkdir()
    fresh_workspace: Optional[Path] = None
    if args.fresh:
        if not candidate_patch_ok(run_dir, candidate):
            raise DispatchError("候选补丁缺失、被改动或未通过往返校验，不能建立干净副本")
        try:
            fresh_workspace = prepare_fresh_workspace(repo, run_dir, meta, contract, candidate, config, out_dir,
                                                      env, grace)
        except (DispatchError, OSError) as exc:
            write_json(out_dir / "checks.json", {"aborted": "fresh_workspace_failed", "error": str(exc),
                                                 "at": utc_now()}, exclusive=True)
            raise DispatchError("无法建立干净的验收副本：%s" % exc)
        work_dir = fresh_workspace
    else:
        work_dir = Path(meta["worktree"])
        if not work_dir.is_dir():
            raise DispatchError("worktree 已不存在：%s；可用 --fresh 在干净副本上验收" % work_dir)
    try:
        tree_before = snapshot_tree(work_dir, meta["base_sha"], out_dir, "before", meta.get("git_autocrlf"))
        drift_before = tree_drift(work_dir, candidate["tree"], tree_before)
        pre_artifacts, pre_unexpected = split_extras(drift_before["added"], artifacts)
        if drift_before["modified"] or pre_unexpected:
            write_json(out_dir / "checks.json", {"aborted": "candidate_drift", "tree_now": tree_before,
                                                 "candidate_tree": candidate["tree"],
                                                 "modified": drift_before["modified"],
                                                 "unexpected_files": pre_unexpected, "at": utc_now()},
                       exclusive=True)
            raise DispatchError(
                "工作副本与候选不一致，检查结果无法代表候选：被修改的候选文件 %s；候选之外的新文件 %s。"
                "删除这些额外文件、重新派遣以固定新候选，或用 --fresh 在干净副本上验收。"
                % (drift_before["modified"][:10] or "无", pre_unexpected[:10] or "无"), EXIT_DRIFT)
        started = utc_now()
        results = []
        for item in checks:
            print("CHECK %s ..." % item["id"], flush=True)
            record = _run_command_item(item, work_dir, env, out_dir, grace)
            results.append(record)
            print("CHECK %s %s %s" % (item["id"], record["status"], record.get("reason") or ""), flush=True)
        tree_after = snapshot_tree(work_dir, meta["base_sha"], out_dir, "after", meta.get("git_autocrlf"))
        drift_after = tree_drift(work_dir, candidate["tree"], tree_after)
        post_artifacts, post_unexpected = split_extras(drift_after["added"], artifacts)
    finally:
        if fresh_workspace is not None and not args.keep_workspace:
            remove_worktree(repo, fresh_workspace)
    all_ids = {c["id"] for c in contract["checks"] if c.get("required", True)}
    ran_ids = {r["id"] for r in results}
    required_ok = all(r["passed"] for r in results if r["required"])
    payload = {"run": number, "mode": "fresh" if args.fresh else "in_place", "workspace": str(work_dir),
               "workspace_kept": bool(args.fresh and args.keep_workspace),
               "started_at": started, "ended_at": utc_now(), "candidate_tree": candidate["tree"],
               "tree_before": tree_before, "tree_after": tree_after,
               "modified_by_checks": bool(drift_after["modified"]),
               "candidate_files_modified": drift_after["modified"],
               "unexpected_files_by_checks": post_unexpected[:200],
               "artifact_files": sorted(set(pre_artifacts) | set(post_artifacts))[:200],
               "covers_all_required": all_ids <= ran_ids, "all_required_passed": required_ok,
               "env_removed": removed, "results": results}
    write_json(out_dir / "checks.json", payload, exclusive=True)
    log_event(run_dir, "checks", run=number, mode=payload["mode"], passed=required_ok,
              covers_all_required=payload["covers_all_required"])
    if payload["modified_by_checks"]:
        print("WARN  检查修改了候选文件：%s（结果不能作为 PASS 证据）" % ", ".join(drift_after["modified"][:10]))
    if post_unexpected:
        print("WARN  检查产生了候选之外的新文件：%s。确属缓存或报告时，加入 .gitignore 或 "
              "dispatch.config.json 的 check_artifact_patterns。" % ", ".join(post_unexpected[:10]))
    print("检查结果（%s）：%s · %s" % (payload["mode"], "全部必要检查通过" if required_ok else "存在失败的必要检查",
                                   display_path(out_dir / "checks.json", repo.root)))
    clean = required_ok and not payload["modified_by_checks"] and not post_unexpected
    return EXIT_OK if clean else EXIT_FAIL


#: 检查日志里这些话说明“目标不存在”，而不是“行为不对”。只用来改写 baseline 的说明文字，不影响判定。
MISSING_TARGET_PATTERNS = (
    r"Could not find", r"no such file", r"ENOENT", r"no tests? (?:found|ran|collected)",
    r"No test files found", r"collected 0 items", r"is not recognized", r"cannot find module",
    r"找不到", r"不存在",
)


def _looks_like_missing_target(out_dir: Path, record: Dict[str, Any]) -> bool:
    """基线上失败的检查，其日志是否只是在说“文件 / 用例不存在”。"""
    log_path = out_dir / ("%s.log" % record.get("id"))
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return any(re.search(pattern, text, re.I) for pattern in MISSING_TARGET_PATTERNS)


def cmd_baseline(args: argparse.Namespace) -> int:
    """派遣前在基线上运行合同检查：用来证明修复的探针应当在基线上失败，否则它区分不了修复前后。

    检查项可以用 expect_on_base 声明期望（fail / pass / any，缺省 any）。结果写入
    .agent/runs/<task-id>/baseline/NN/，不创建 attempt，不计入预算。
    """
    repo = Repo.discover(args.repo)
    key = plan_key_from_arg(repo, args.plan_key)
    contract, errors, warnings = validate_plan(repo, key)
    _print_messages(errors, warnings)
    if errors or contract is None:
        raise DispatchError("合同校验失败，无法运行基线检查。", EXIT_USAGE)
    checks = contract["checks"]
    if args.only:
        wanted = [x.strip() for x in args.only.split(",") if x.strip()]
        unknown = [x for x in wanted if x not in {c["id"] for c in checks}]
        if unknown:
            raise DispatchError("未知检查：%s" % ", ".join(unknown), EXIT_USAGE)
        checks = [c for c in checks if c["id"] in wanted]
    if not checks:
        raise DispatchError("合同没有可运行的检查", EXIT_USAGE)
    config = repo.config()
    env, removed = child_env(config)
    grace = float(config.get("kill_grace_seconds", 15))
    out_root = repo.runs_dir / contract["task_id"] / "baseline"
    out_root.mkdir(parents=True, exist_ok=True)
    number = _next_number(out_root)
    out_dir = out_root / ("%02d" % number)
    out_dir.mkdir()
    root = repo.worktree_root(config)
    root.mkdir(parents=True, exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix="%s-%s-baseline-" % (repo.root.name[:16], contract["task_id"][:24]),
                                      dir=str(root))).resolve()
    results: List[Dict[str, Any]] = []
    started = utc_now()
    try:
        git(["worktree", "add", "--detach", str(workspace), contract["base_sha"]], repo.root)
        for item in contract["setup"]:
            record = _run_command_item(item, workspace, env, out_dir, grace)
            if not record["passed"]:
                raise DispatchError("基线副本的 setup %s 失败：%s" % (item["id"], record.get("reason")))
        for item in checks:
            print("BASELINE %s ..." % item["id"], flush=True)
            results.append(_run_command_item(item, workspace, env, out_dir, grace))
    finally:
        if not args.keep_workspace:
            remove_worktree(repo, workspace)
    mismatches: List[str] = []
    rows: List[Tuple[str, str, str, str]] = []
    expectations = {c["id"]: c.get("expect_on_base", "any") for c in contract["checks"]}
    for record in results:
        expect = expectations.get(record["id"], "any")
        outcome = "passed" if record["passed"] else record["status"]
        if expect == "fail" and record["passed"]:
            note = "不符：期望在基线上失败，实际已通过——这个探针区分不了修复前后"
            mismatches.append(record["id"])
        elif expect == "pass" and not record["passed"]:
            note = "不符：期望在基线上通过（回归保护），实际未通过——检查本身或基线有问题"
            mismatches.append(record["id"])
        elif expect == "any" and record["passed"]:
            note = "基线上已通过（回归保护属正常；若用来证明修复，标注 expect_on_base: fail 并改写）"
        else:
            note = "符合预期" if expect != "any" else "基线上未通过（修复后应通过）"
            if expect == "any" and _looks_like_missing_target(out_dir, record):
                note = ("基线上未通过：输出显示找不到文件或用例——只新增测试文件的合同在基线上本就如此，属正常；"
                        "有效性改用变异检查证明")
        rows.append((record["id"], expect, outcome, note))
    payload = {"plan_key": key, "base_sha": contract["base_sha"], "started_at": started, "ended_at": utc_now(),
               "workspace": str(workspace), "workspace_kept": bool(args.keep_workspace), "env_removed": removed,
               "mismatches": mismatches, "results": results}
    write_json(out_dir / "checks.json", payload, exclusive=True)
    widths = [max(len(r[i]) for r in rows + [("CHECK", "EXPECT", "BASE", "")]) for i in range(3)]
    print("  ".join(h.ljust(widths[i]) for i, h in enumerate(("CHECK", "EXPECT", "BASE"))) + "  NOTE")
    for row in rows:
        print("  ".join(row[i].ljust(widths[i]) for i in range(3)) + "  " + row[3])
    print("基线检查记录：%s" % display_path(out_dir / "checks.json", repo.root))
    return EXIT_FAIL if mismatches else EXIT_OK


def evaluate_gates(repo: Repo, run_dir: Path, meta: Dict[str, Any], contract: Dict[str, Any]) -> Dict[str, Any]:
    gates: Dict[str, Dict[str, Any]] = {g: {"passed": True, "problems": [], "notes": []} for g in GATES}
    gates["G5"]["notes"].append("质量复审（测试是否弱化、兼容性、残余风险）由复审报告负责，工具不做机械判断")

    def fail(gate: str, message: str) -> None:
        gates[gate]["passed"] = False
        gates[gate]["problems"].append(message)

    for problem in verify_inputs(run_dir, meta):
        fail("G0", problem)
    if resolve_commit(repo.root, meta["base_sha"]) != meta["base_sha"]:
        fail("G0", "基线提交不可用")
    state = get_state(run_dir)
    run = read_json_or(run_dir / "run.json", {})
    events = read_json_or(run_dir / "events-summary.json", {})
    if not run:
        fail("G1", "缺少 run.json")
    if run.get("timed_out"):
        fail("G1", "运行超时")
    if run.get("interrupted"):
        fail("G1", "运行被取消或调度器中断")
    if run.get("exit_code") != 0:
        fail("G1", "Pi 退出码为 %s" % run.get("exit_code"))
    for problem in events.get("problems", ["缺少事件摘要"]):
        fail("G1", problem)
    if events and not events.get("provider_thinking_levels"):
        gates["G1"]["notes"].append("提供商未回报思考级别：只能确认请求的级别（%s）"
                                    % (events.get("requested_model") or {}).get("thinking"))
    report = read_json_or(run_dir / "report-status.json", {})
    if report.get("status") != "json_ok":  # 执行器自述是最低优先级证据，缺失只作提示
        gates["G1"]["notes"].append("执行报告状态：%s" % report.get("status"))
    if report.get("contract_conflicts"):
        gates["G3"]["notes"].append("执行报告列出了 %d 处合同矛盾：PASS 前在复审中逐条裁定"
                                    % report["contract_conflicts"])
    elif events.get("ambiguity_mention_count") and not report.get("unresolved_questions"):
        gates["G3"]["notes"].append("执行过程中提到合同的歧义、矛盾或一致性，报告没有列出：复审时核对（见 summary.md）")
    scope = read_json_or(run_dir / "scope.json", None)
    if scope is None:
        fail("G2", "缺少 scope.json")
    else:
        for violation in scope.get("violations", []):
            fail("G2", "%s %s" % (violation["kind"], violation["path"]))
    changes = read_json_or(run_dir / "observations.json", {}).get("main_repo_changes") or {}
    if changes.get("head_changed") or changes.get("other_paths"):
        gates["G2"]["notes"].append("运行期间主工作区有规划路径之外的变化，复审时确认来源（见 summary.md）")
    for item in events.get("outside_worktree_paths", []):
        if item.get("failed") is not True:
            gates["G2"]["notes"].append("执行器访问了工作副本外路径：%s（%s）" % (item.get("path"), item.get("tool")))
    candidate = read_json_or(run_dir / "candidate.json", {})
    latest = _latest_numbered(run_dir / "checks")
    checks = read_json_or(latest / "checks.json", None) if latest else None
    if not checks or checks.get("aborted"):
        fail("G3", "没有有效的独立检查记录")
        fail("G4", "没有有效的独立检查记录")
    else:
        results = {r["id"]: r for r in checks.get("results", [])}
        if checks.get("candidate_tree") != candidate.get("tree"):
            fail("G4", "最近一次检查不是针对当前候选")
        if not checks.get("covers_all_required"):
            fail("G4", "最近一次检查没有覆盖全部必要检查（使用了 --only？）")
        if checks.get("modified_by_checks"):
            fail("G4", "检查过程修改了候选文件：%s" % ", ".join(checks.get("candidate_files_modified", [])[:10]))
        if checks.get("unexpected_files_by_checks"):
            fail("G4", "检查产生了候选之外的新文件：%s" % ", ".join(checks["unexpected_files_by_checks"][:10]))
        if checks.get("artifact_files"):
            gates["G4"]["notes"].append("忽略的缓存文件：%s" % ", ".join(checks["artifact_files"][:10]))
        if checks.get("mode") == "fresh":
            gates["G4"]["notes"].append("检查在干净副本（基线 + 候选补丁 + setup）上运行")
        else:
            gates["G4"]["notes"].append("检查在执行 worktree 中运行：被 .gitignore 忽略的文件（依赖、构建产物）"
                                        "也可能影响结果；中高风险任务建议 check --fresh")
        for check in contract["checks"]:
            if check.get("required", True):
                record = results.get(check["id"])
                if not record or not record.get("passed"):
                    fail("G4", "必要检查 %s：%s" % (check["id"], record.get("status") if record else "not_run"))
        for item in contract["definition_of_done"]:
            for ref in item.get("evidence", []):
                if ref == "scope":
                    if scope is None or scope.get("violations"):
                        fail("G3", "%s 依赖的范围证据未通过" % item["id"])
                elif ref != "review":
                    record = results.get(ref)
                    if not record or not record.get("passed"):
                        fail("G3", "%s 依赖的 %s 未通过或未运行" % (item["id"], ref))
    work_dir = Path(meta["worktree"])
    if candidate.get("tree") and work_dir.is_dir():
        try:
            now = snapshot_tree(work_dir, meta["base_sha"], run_dir, "gate", meta.get("git_autocrlf"))
            drift = tree_drift(work_dir, candidate["tree"], now)
            if drift["modified"]:
                if line_endings_only(work_dir, candidate["tree"], now):
                    fail("G6", "候选文件与记录只差行尾（CRLF / LF）：%d 个文件。多半是 core.autocrlf 在运行后被改动"
                                "（prepare 时记录 %s，现在 %s）；先恢复配置再重新 verdict"
                         % (len(drift["modified"]), meta.get("git_autocrlf", "未记录"), effective_autocrlf(repo.root)))
                else:
                    fail("G6", "候选文件在记录后被修改：%s" % ", ".join(drift["modified"][:10]))
            if drift["added"]:
                gates["G6"]["notes"].append("工作副本有候选之外的新文件（不会被集成）：%s"
                                            % ", ".join(drift["added"][:10]))
        except DispatchError as exc:
            fail("G6", "无法重新快照：%s" % exc)
    if not candidate_patch_ok(run_dir, candidate):
        fail("G6", "候选补丁缺失、被改动或未通过往返校验")
    return {"state_at_review": state, "gates": gates}


def cmd_verdict(args: argparse.Namespace) -> int:
    repo = Repo.discover(args.repo)
    run_dir = resolve_run_dir(repo, args.run_dir)
    meta, contract = load_attempt(repo, run_dir)
    state = get_state(run_dir)
    if state not in REVIEWABLE_STATES:
        raise DispatchError("状态 %s 不能记录验收结论" % state)
    verdict = args.verdict
    review_path = Path(args.review)
    if not review_path.is_file() or review_path.stat().st_size == 0:
        raise DispatchError("找不到复审报告：%s" % review_path, EXIT_USAGE)
    review_text = review_path.read_text(encoding="utf-8")
    declared = re.search(r"^\s*Verdict:\s*([A-Z_]+)\s*$", review_text, re.M)
    if not declared or declared.group(1) != verdict:
        raise DispatchError("复审报告中的 'Verdict:' 行必须恰好是 %s" % verdict, EXIT_USAGE)
    waivers: Dict[str, str] = {}
    for item in args.waive or []:
        gate, _, reason = item.partition("=")
        if gate not in GATES or not reason.strip():
            raise DispatchError("--waive 格式应为 G2=原因", EXIT_USAGE)
        waivers[gate] = reason.strip()
    evaluation = evaluate_gates(repo, run_dir, meta, contract)
    failed = [g for g, info in evaluation["gates"].items() if not info["passed"]]
    for note in evaluation["gates"]["G3"]["notes"]:  # 合同矛盾一类的提示：下结论前应已在复审中裁定
        print("NOTE  G3 %s" % note)
    if verdict == "PASS":
        if failed:
            for gate in failed:
                for problem in evaluation["gates"][gate]["problems"]:
                    print("GATE %s %s" % (gate, problem))
            raise DispatchError("PASS 被拒绝：门禁 %s 未通过。修正后重新验收，或按授权使用 "
                                "ACCEPTED_WITH_EXCEPTION 并逐项豁免。" % ", ".join(failed), EXIT_FAIL)
        if waivers:
            raise DispatchError("PASS 不接受豁免；有豁免时使用 ACCEPTED_WITH_EXCEPTION", EXIT_USAGE)
    elif verdict == "ACCEPTED_WITH_EXCEPTION":
        missing = [g for g in failed if g not in waivers]
        if missing:
            raise DispatchError("以下失败门禁没有豁免理由：%s" % ", ".join(missing), EXIT_USAGE)
        if not waivers or not args.decided_by:
            raise DispatchError("ACCEPTED_WITH_EXCEPTION 需要至少一项 --waive 与 --decided-by", EXIT_USAGE)
    elif not args.failure_class:
        raise DispatchError("%s 需要 --class（%s）" % (verdict, ", ".join(FAILURE_CLASSES)), EXIT_USAGE)
    verdict_dir = run_dir / "verdicts"
    verdict_dir.mkdir(exist_ok=True)
    number = _next_number(verdict_dir)
    review_copy = verdict_dir / ("%02d.md" % number)
    shutil.copyfile(str(review_path), str(review_copy))
    record = {"number": number, "verdict": verdict, "failure_class": args.failure_class,
              "decided_by": args.decided_by, "waivers": waivers, "human_minutes": args.human_minutes,
              "note": args.note, "review_source": str(review_path), "review_sha256": sha256_file(review_copy),
              "candidate_tree": read_json_or(run_dir / "candidate.json", {}).get("tree"),
              "gates": evaluation["gates"], "state_before": state, "recorded_at": utc_now()}
    write_json(verdict_dir / ("%02d.json" % number), record, exclusive=True)
    set_state(run_dir, verdict, verdict_no=number, failure_class=args.failure_class)
    print("%s 已记录（%s）。" % (verdict, display_path(verdict_dir / ("%02d.json" % number), repo.root)))
    if failed and verdict != "PASS":
        print("未通过的门禁：%s" % ", ".join(failed))
    return EXIT_OK


def latest_verdict(run_dir: Path) -> Dict[str, Any]:
    directory = run_dir / "verdicts"
    if not directory.is_dir():
        return {}
    files = sorted(directory.glob("*.json"), key=lambda p: int(p.stem))
    return read_json_or(files[-1], {}) if files else {}


def cmd_branch(args: argparse.Namespace) -> int:
    repo = Repo.discover(args.repo)
    run_dir = resolve_run_dir(repo, args.run_dir)
    meta, contract = load_attempt(repo, run_dir)
    problems = verify_inputs(run_dir, meta)
    if problems:
        raise DispatchError("输入不一致（G0）：%s" % "；".join(problems))
    require_authorized_action(contract, "local_branch", integration=True)
    verdict = latest_verdict(run_dir).get("verdict")
    if verdict not in PASSING_VERDICTS and not (args.rework and verdict == "REVISE"):
        raise DispatchError("最新结论为 %s：只有 PASS / ACCEPTED_WITH_EXCEPTION（或 --rework 时的 REVISE）"
                            "可以建分支。" % verdict)
    # 身份与尾注先核对：之后才会按补丁重建候选树、写 Git 对象、建分支。
    identity = git_identity_problem(repo.root)
    if identity:
        raise DispatchError(identity)
    trailers = [] if args.no_config_trailers else commit_trailers(repo.config())
    for extra in args.trailer or []:
        if not valid_trailer(extra):
            raise DispatchError("--trailer 必须是单行 `Key: value`，不能含回车、换行等控制字符：%r" % extra, EXIT_USAGE)
        trailers.append(extra)
    candidate = read_json_or(run_dir / "candidate.json", {})
    tree = candidate.get("tree")
    if not tree:
        raise DispatchError("缺少候选记录")
    if git(["cat-file", "-e", tree + "^{tree}"], repo.root, check=False).returncode != 0:
        rebuilt = tree_from_patch(repo.root, meta["base_sha"], run_dir / "candidate.patch", run_dir,
                                  meta.get("git_autocrlf"))
        if rebuilt != tree:
            raise DispatchError("候选树对象已丢失，且补丁重建结果不一致")
    prefix = "pi-rework" if args.rework else "pi"
    name = args.name or "%s/%s-v%s-a%03d" % (prefix, meta["task_id"], meta["plan_version"], meta["attempt_no"])
    if git(["check-ref-format", "--branch", name], repo.root, check=False).returncode != 0:
        raise DispatchError("分支名不合法：%s" % name, EXIT_USAGE)
    if git(["rev-parse", "--verify", "--quiet", "refs/heads/" + name], repo.root, check=False).returncode == 0:
        raise DispatchError("分支已存在：%s" % name)
    raw_contract = read_json_or(run_dir / "contract.json", {})
    title = raw_contract.get("title") if isinstance(raw_contract, dict) else None
    executor = read_json_or(run_dir / "executor.json", {})
    subject = branch_subject(meta["task_id"], title, meta["plan_version"], meta["attempt_no"])
    lines = [subject, "",
             "Pi-Dispatch-Attempt: %s" % meta["attempt_id"],
             "Pi-Executor: %s/%s (thinking %s)" % (executor.get("provider"), executor.get("model"),
                                                   executor.get("thinking")),
             "Candidate-Tree: %s" % tree,
             "Verdict: %s" % verdict]
    if trailers:
        lines += [""] + trailers
    message = "\n".join(lines) + "\n"
    message_file = run_dir / "branch-message.txt"
    # 以字节写入：Windows 的文本模式会把换行写成 CRLF，commit-tree 会原样写进提交说明。
    message_file.write_bytes(message.encode("utf-8"))
    commit = git_text(["commit-tree", tree, "-p", meta["base_sha"], "-F", str(message_file)], repo.root)
    git(["branch", name, commit], repo.root)
    record = {"branch": name, "commit": commit, "tree": tree, "verdict": verdict, "rework": bool(args.rework),
              "created_at": utc_now()}
    write_json(run_dir / ("branch-%s.json" % re.sub(r"[^A-Za-z0-9._-]", "_", name)), record)
    log_event(run_dir, "branch_created", **record)
    print("已创建本地分支 %s → %s（未推送）。" % (name, commit))
    print("commit=%s branch=%s" % (commit, name))
    if args.rework:
        print("返工合同可把 base_sha 设为 %s，从该候选继续。" % commit)
    else:
        head = git_text(["rev-parse", "HEAD"], repo.root)
        if head == meta["base_sha"]:
            print("集成：HEAD 仍是基线，可以 git merge --ff-only %s" % name)
        else:
            print("集成：HEAD（%s）已比基线前进，用 git cherry-pick %s（父提交是基线，不能 ff-only）"
                  % (head[:12], commit[:12]))
    return EXIT_OK


def cmd_mark(args: argparse.Namespace) -> int:
    repo = Repo.discover(args.repo)
    run_dir = resolve_run_dir(repo, args.run_dir)
    state = get_state(run_dir)
    if args.state == "INTEGRATED":
        if latest_verdict(run_dir).get("verdict") not in PASSING_VERDICTS:
            raise DispatchError("只有通过验收的候选可以标记为 INTEGRATED；候选已并入后续提交（返工或规划器补齐）"
                                "时用 SUPERSEDED")
        if not args.ref:
            raise DispatchError("INTEGRATED 需要 --ref（提交、PR 或合并记录）", EXIT_USAGE)
    elif args.state == "SUPERSEDED":
        # 候选没有单独通过验收，但已经并入后续提交：例如返工基线上的新版本通过后一起集成，
        # 或预算用尽后由规划器补齐剩余部分再集成。它不再是“待集成”，也不是被放弃。
        if state not in ("REVISE", "ESCALATE", "BLOCKED", "NEEDS_REVIEW", "TIMEOUT", "CANCELLED", "INFRA_FAILURE"):
            raise DispatchError("SUPERSEDED 只用于已结束、尚未集成的 attempt（当前 %s）" % state, EXIT_USAGE)
        if not args.ref or not args.reason:
            raise DispatchError("SUPERSEDED 需要 --ref（包含该候选的提交）与 --reason（由谁、怎样收尾）", EXIT_USAGE)
    elif state in ("RUNNING", "COLLECTING", "PREPARING"):
        # 调度器异常退出后可能停在这些状态；只有确认没有进程在运行时才允许放弃。
        if not args.force:
            raise DispatchError("attempt 处于 %s；如果确认调度器已退出，可加 --force 放弃" % state)
        pid_file = run_dir / "pid.txt"
        pid_text = pid_file.read_text(encoding="utf-8").strip() if pid_file.exists() else ""
        if pid_text.isdigit() and pid_alive(int(pid_text)):
            raise DispatchError("记录的 Pi 进程 %s 仍在运行，不能放弃" % pid_text)
    set_state(run_dir, args.state, ref=args.ref, reason=args.reason, previous_state=state)
    print("%s 已标记为 %s。" % (display_path(run_dir, repo.root), args.state))
    return EXIT_OK


def _registered_worktrees(repo: Repo) -> List[str]:
    listing = git(["worktree", "list", "--porcelain"], repo.root).stdout.decode("utf-8", "replace")
    return [line[len("worktree "):] for line in listing.splitlines() if line.startswith("worktree ")]


def cmd_cleanup(args: argparse.Namespace) -> int:
    repo = Repo.discover(args.repo)
    run_dir = resolve_run_dir(repo, args.run_dir)
    meta, _contract = load_attempt(repo, run_dir)
    state = get_state(run_dir)
    if state in ("RUNNING", "COLLECTING"):
        raise DispatchError("attempt 正在运行或收集（%s），不能清理；调度器已退出时先 collect --recover" % state)
    if state in ("PREPARED", "PREPARING") and not args.force:
        raise DispatchError("attempt 尚未运行（%s）；确定放弃请加 --force" % state)
    registered = _registered_worktrees(repo)

    def is_registered(path: Path) -> bool:
        return any(norm_case(item) == norm_case(str(path)) for item in registered)

    work_dir = Path(meta["worktree"])
    lost: List[str] = []
    if is_registered(work_dir):
        candidate = read_json_or(run_dir / "candidate.json", {})
        if not candidate.get("tree"):
            lost.append("没有候选记录：worktree 中的全部改动都会丢失")
        else:
            if not candidate_patch_ok(run_dir, candidate):
                lost.append("候选补丁缺失、被改动或未通过往返校验：删除后无法重建候选")
            try:
                now = snapshot_tree(work_dir, meta["base_sha"], run_dir, "cleanup", meta.get("git_autocrlf"))
                drift = tree_drift(work_dir, candidate["tree"], now)
                _artifacts, unexpected = split_extras(drift["added"], artifact_matchers(repo.config()))
                if drift["modified"]:
                    lost.append("候选记录之后被修改的文件：%s" % ", ".join(drift["modified"][:20]))
                if unexpected:
                    lost.append("候选之外的新文件：%s" % ", ".join(unexpected[:20]))
            except DispatchError as exc:
                lost.append("无法核对 worktree 内容：%s" % exc)
        if lost and not args.force:
            for item in lost:
                print("LOSS  %s" % item)
            raise DispatchError("拒绝清理：以上内容不在已保存的候选中，删除 worktree 会丢失它们。"
                                "先保存需要的内容；确认放弃请加 --force。")
        git(["worktree", "remove", "--force", str(work_dir)], repo.root)
        print("已移除 worktree：%s" % work_dir)
    elif work_dir.exists() and any(work_dir.iterdir()):
        raise DispatchError("%s 存在但不是本仓库登记的 worktree，拒绝删除" % work_dir)
    else:
        print("worktree 已不存在或未创建：%s" % work_dir)
    # 保留下来的干净验收副本（check --fresh --keep-workspace）不含独有内容，一并移除。
    for checks_file in sorted((run_dir / "checks").glob("*/checks.json")) if (run_dir / "checks").is_dir() else []:
        record = read_json_or(checks_file, {})
        workspace = Path(record.get("workspace", "")) if record.get("workspace_kept") else None
        if workspace is not None and is_registered(workspace):
            remove_worktree(repo, workspace)
            print("已移除验收副本：%s" % workspace)
    log_event(run_dir, "cleanup", worktree=str(work_dir), state=state, forced=bool(args.force), discarded=lost)
    return EXIT_OK


def _attempt_row(repo: Repo, run_dir: Path) -> Dict[str, Any]:
    meta = read_json_or(run_dir / "meta.json", {})
    run = read_json_or(run_dir / "run.json", {})
    events = read_json_or(run_dir / "events-summary.json", {})
    scope = read_json_or(run_dir / "scope.json", {})
    latest = _latest_numbered(run_dir / "checks")
    checks = read_json_or(latest / "checks.json", {}) if latest else {}
    results = checks.get("results", [])
    verdict = latest_verdict(run_dir)
    cost = events.get("cost") or {}
    return {
        "attempt": display_path(run_dir, repo.runs_dir), "task_id": meta.get("task_id"),
        "plan_version": meta.get("plan_version"), "attempt_no": meta.get("attempt_no"),
        "state": get_state(run_dir), "started": (run_dir / "claim").is_dir(), "exit_code": run.get("exit_code"),
        "wall_seconds": run.get("wall_seconds"), "events_ok": events.get("ok"),
        "violations": len(scope.get("violations", [])) if scope else None,
        "checks": "%d/%d" % (sum(1 for r in results if r.get("passed")), len(results)) if results else "-",
        "check_mode": checks.get("mode"),
        "verdict": verdict.get("verdict"), "failure_class": verdict.get("failure_class"),
        "human_minutes": verdict.get("human_minutes"),
        "tokens": (events.get("usage") or {}).get("totalTokens"),
        "cost": cost.get("total"), "cost_status": cost.get("status") if events else None,
    }


def _format_cost(row: Dict[str, Any]) -> str:
    if row["cost_status"] is None:
        return "-"
    if row["cost"] is None:
        return "unknown"
    return "%s(%s)" % (row["cost"], row["cost_status"])


#: 上次工具调用之后的消息增量事件达到该数时，live 状态提示“长时间没有工具调用”。
#: 按 45 次实机运行标定：这类长段几乎全是思考增量；正常运行中最长的一段在 4200 个以内，
#: 超过 6000 的 4 次都是用时最长的运行（1200 秒以上），其中 2 次超时。原阈值 2000 在
#: 大多数运行里都会出现，开跑两分钟的正常思考也会被提示。
LONG_THINKING_DELTAS = 6000


def _live_progress(run_dir: Path) -> Optional[str]:
    """运行中的 attempt：已完成的工具调用次数与已用时间（只读事件文件，不解析 JSON）。

    上次工具调用之后的消息增量事件很多时，另外提示“长时间没有工具调用”：执行器可能
    在长时间思考或输出，运行中无法干预，但可以据此预估是否会超时、准备下一版合同。
    """
    try:
        data = (run_dir / "events.jsonl").read_bytes()
    except OSError:
        data = b""
    started = read_json_or(run_dir / "run-started.json", {}).get("started_at")
    elapsed = ""
    if started:
        try:
            begin = _dt.datetime.strptime(started, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_dt.timezone.utc)
            elapsed = " %ds" % (_dt.datetime.now(_dt.timezone.utc) - begin).total_seconds()
        except ValueError:
            elapsed = ""
    marker = b'"type":"tool_execution_end"'
    last_tool = data.rfind(marker)
    tail = data[last_tool:] if last_tool >= 0 else data
    deltas = tail.count(b'"type":"message_update"')
    quiet = " 长时间没有工具调用（%d 个增量）" % deltas if deltas >= LONG_THINKING_DELTAS else ""
    return "live:%dt%s%s" % (data.count(marker), elapsed, quiet)


def cmd_status(args: argparse.Namespace) -> int:
    repo = Repo.discover(args.repo)
    target = args.task_id
    if target and not TASK_ID_RE.match(target):
        # attempt 路径、task-id/attempt-NNN 或 task-id.vN：只显示解析到的那一个 attempt。
        attempts = [resolve_run_dir(repo, target)]
    else:
        tasks = [target] if target else (
            sorted(d.name for d in repo.runs_dir.iterdir() if d.is_dir()) if repo.runs_dir.is_dir() else [])
        attempts = [attempt for task in tasks for attempt in task_attempts(repo, task)]
    rows = [_attempt_row(repo, attempt) for attempt in attempts]
    for row, attempt in zip(rows, attempts):
        if row["state"] == "RUNNING":
            row["events_ok"] = _live_progress(attempt)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return EXIT_OK
    if not rows:
        print("没有 attempt 记录。")
        return EXIT_OK
    header = ("ATTEMPT", "STATE", "EXIT", "EVENTS", "VIOL", "CHECKS", "VERDICT", "WALL(s)", "COST")
    table = [header] + [(r["attempt"], r["state"], str(r["exit_code"]), str(r["events_ok"]), str(r["violations"]),
                         r["checks"], str(r["verdict"] or "-"), str(r["wall_seconds"] or "-"), _format_cost(r))
                        for r in rows]
    widths = [max(len(str(row[i])) for row in table) for i in range(len(header))]
    for row in table:
        print("  ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row)))
    return EXIT_OK


def safe_output_path(args: argparse.Namespace) -> Optional[Path]:
    """--out 只能写到 .agent/runs/_env/ 或 .agent/runs/_reports/ 下，不能覆盖仓库文件或 attempt 证据。"""
    if not getattr(args, "out", None):
        return None
    repo = Repo.discover(args.repo)
    target = Path(args.out)
    target = (target if target.is_absolute() else Path.cwd() / target).resolve()
    allowed = [(repo.runs_dir / "_env").resolve(), (repo.runs_dir / "_reports").resolve()]
    if not any(is_within(target, root) and norm_case(str(target)) != norm_case(str(root)) for root in allowed):
        raise DispatchError("--out 只能指向 .agent/runs/_env/ 或 .agent/runs/_reports/ 下的文件：%s" % target,
                            EXIT_USAGE)
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def cmd_metrics(args: argparse.Namespace) -> int:
    out_path = safe_output_path(args)
    repo = Repo.discover(args.repo)
    tasks = sorted(d.name for d in repo.runs_dir.iterdir() if d.is_dir()) if repo.runs_dir.is_dir() else []
    per_task = []
    for task in tasks:
        rows = [_attempt_row(repo, a) for a in task_attempts(repo, task)]
        started = [r for r in rows if r["started"]]
        if not started:
            continue
        verdicts = [r["verdict"] for r in started]
        known_costs = [r["cost"] for r in started if r["cost"] is not None]
        per_task.append({
            "task_id": task, "attempts": len(started),
            "first_attempt_pass": verdicts[0] == "PASS",
            "passed": "PASS" in verdicts,
            "accepted_with_exception": "PASS" not in verdicts and "ACCEPTED_WITH_EXCEPTION" in verdicts,
            "violation_any": any((r["violations"] or 0) > 0 for r in started),
            "wall_seconds": round(sum(r["wall_seconds"] or 0 for r in started), 1),
            "tokens": sum(r["tokens"] or 0 for r in started),
            "known_cost": round(sum(known_costs), 6) if known_costs else None,
            "unknown_cost_attempts": sum(1 for r in started if r["cost"] is None or r["cost_status"] != "estimated"),
            "human_minutes": sum(r["human_minutes"] or 0 for r in started),
            "failure_classes": sorted({r["failure_class"] for r in started if r["failure_class"]}),
        })
    total = len(per_task)
    rate = lambda n: "%.0f%%" % (100.0 * n / total) if total else "-"  # noqa: E731
    known_total = sum(t["known_cost"] or 0 for t in per_task)
    unknown_attempts = sum(t["unknown_cost_attempts"] for t in per_task)
    lines = ["# Pi 执行试运行指标", "", "生成时间：%s · 任务数：%d" % (utc_now(), total), "",
             "PASS 与 ACCEPTED_WITH_EXCEPTION 分开统计：通过率只计 PASS。", "",
             "| 指标 | 数值 |", "|---|---|",
             "| 首次验收通过率（PASS） | %s |" % rate(sum(t["first_attempt_pass"] for t in per_task)),
             "| 有限重试内通过率（PASS） | %s |" % rate(sum(t["passed"] for t in per_task)),
             "| 豁免接受（ACCEPTED_WITH_EXCEPTION）任务 | %d |" % sum(t["accepted_with_exception"] for t in per_task),
             "| 未通过任务 | %d |" % sum(1 for t in per_task if not t["passed"] and not t["accepted_with_exception"]),
             "| 越界率 | %s |" % rate(sum(t["violation_any"] for t in per_task)),
             "| 执行轮次合计 | %d |" % sum(t["attempts"] for t in per_task),
             "| 已知执行费用（估算，仅 Pi 执行端） | %.4f%s |" % (
                 known_total, "（另有 %d 轮费用未知或不完整，实际更高）" % unknown_attempts if unknown_attempts else ""),
             "| 人工介入分钟 | %s |" % sum(t["human_minutes"] for t in per_task), "",
             "规划与复审（规划端）费用不在此表，请按同一口径另行记录后再比较（方案第 13 节）。", "",
             "| 任务 | 轮次 | 首轮 PASS | 最终结果 | 越界 | 墙钟(s) | tokens | 已知费用 | 失败分类 |",
             "|---|---|---|---|---|---|---|---|---|"]
    for t in per_task:
        outcome = "PASS" if t["passed"] else ("豁免接受" if t["accepted_with_exception"] else "未通过")
        cost_text = "unknown" if t["known_cost"] is None else "%s%s" % (
            t["known_cost"], "（不完整）" if t["unknown_cost_attempts"] else "")
        lines.append("| %s | %d | %s | %s | %s | %s | %s | %s | %s |" % (
            t["task_id"], t["attempts"], "是" if t["first_attempt_pass"] else "否", outcome,
            "是" if t["violation_any"] else "否", t["wall_seconds"], t["tokens"], cost_text,
            ", ".join(t["failure_classes"]) or "-"))
    text = "\n".join(lines) + "\n"
    if out_path is not None:
        out_path.write_text(text, encoding="utf-8")
        print("已写入 %s" % out_path)
    else:
        print(text)
    return EXIT_OK


def cmd_doctor(args: argparse.Namespace) -> int:
    """环境事实。不调用模型，不修改仓库；--out 只能写到 .agent/runs/_env/ 或 _reports/。"""
    out_path = safe_output_path(args)
    facts: Dict[str, Any] = {"generated_at": utc_now(), "tool_version": TOOL_VERSION,
                             "platform": platform.platform(), "machine": platform.machine(),
                             "python": platform.python_version()}
    problems: List[str] = []
    notes: List[str] = []
    code, out, err = run_capture(["git", "--version"])
    facts["git"] = out.strip() or err.strip()
    if code != 0:
        problems.append("git 不可用")
    planners = {}
    for tool_name, fact_key in (("claude", "claude_code"), ("codex", "codex")):
        tool_path = shutil.which(tool_name)
        if tool_path:
            planners[fact_key] = run_capture([tool_path, "--version"], timeout=30)[1].strip()
    facts.update(planners)
    if not planners:
        notes.append("PATH 中没有 claude 或 codex（在规划端会话内运行时可忽略）")
    pi_bin = pi_agent_dir() / "bin"
    for tool in ("rg", "fd"):
        if not shutil.which(tool) and not any((pi_bin / name).is_file() for name in (tool, tool + ".exe")):
            notes.append("未找到 %s：Pi 的 grep/find 工具首次使用时会从 GitHub 下载到 ~/.pi/agent/bin" % tool)
    try:
        pi_cmd = resolve_pi_command()
        facts["pi_command"] = pi_cmd
        code, out, err = run_capture(pi_cmd + ["--version"], timeout=60)
        facts["pi_version"] = (out or err).strip()
        version = parse_version(facts["pi_version"])
        if not version:
            problems.append("无法读取 pi 版本")
        elif version < MIN_PI_VERSION:
            notes.append("pi 版本低于 %s，建议升级" % ".".join(map(str, MIN_PI_VERSION)))
        code, out, err = run_capture(pi_cmd + RESOURCE_FLAGS + ["--help"], timeout=90)
        info = parse_help(out + err)
        facts["pi_help"] = {"thinking_levels": info["thinking_levels"], "builtin_tools": info["builtin_tools"],
                            "required_flags_missing": [f for f in REQUIRED_PI_FLAGS + ["--no-context-files"]
                                                       if f not in info["flags"]]}
        if facts["pi_help"]["required_flags_missing"]:
            problems.append("pi 缺少参数：%s" % ", ".join(facts["pi_help"]["required_flags_missing"]))
        if args.provider and args.model:
            code, out, err = run_capture(pi_cmd + RESOURCE_FLAGS + ["--list-models", args.model], timeout=90)
            rows = list_models_rows(out)
            empty = None if rows else list_models_empty_reason(out)
            # 错误输出先脱敏再截取：Pi 转述 models.json 的解析错误时可能带出其中的凭据。
            facts["executor_model_list"] = {"exit_code": code, "rows": len(rows), "empty_reason": empty,
                                            "stderr_tail": redact_secrets((err or "").strip())[-300:]}
            if code != 0:
                facts["executor_model_listed"] = None
                problems.append("pi --list-models 执行失败（退出码 %s）：%s。在 Codex 等沙箱中运行时，沙箱可能阻止了 pi "
                                "读取配置或联网：改在沙箱外运行 doctor 再判断"
                                % (code, redact_secrets((err or out).strip())[:200]))
            else:
                facts["executor_model_listed"] = (args.provider, args.model) in rows
                if not facts["executor_model_listed"]:
                    problems.append("执行模型 %s/%s 不在可用模型列表中%s" % (args.provider, args.model, {
                        "no_models": "（pi 没有任何可用模型：可能读不到 ~/.pi/agent 的配置或凭据，例如在沙箱中运行；"
                                     "改在沙箱外运行 doctor 再判断）",
                        "no_match": "（pi 有可用模型，但没有与 %s 匹配的）" % args.model,
                    }.get(empty or "", "")))
            # --no-refresh：doctor 不刷新、不改写凭据；过期的 OAuth 令牌会在真正运行时刷新。
            code, out, err = run_capture(pi_cmd + ["auth", "check", "--provider", args.provider, "--model",
                                                   args.model, "--json", "--no-refresh"], timeout=90)
            facts["executor_auth_check"] = {"exit_code": code, "output": redact_secrets((out or err).strip())[:2000],
                                            "refresh": False}
            if code != 0:
                problems.append("执行模型凭据未就绪（pi auth check --no-refresh 退出码 %s）" % code)
            if args.thinking and args.thinking not in info["thinking_levels"]:
                problems.append("思考级别 %s 不受本机 pi 支持" % args.thinking)
    except DispatchError as exc:
        problems.append(str(exc))
    try:
        repo = Repo.discover(args.repo)
        root = repo.root
        head = git_text(["rev-parse", "HEAD"], root)
        facts["repository"] = {
            "root": str(root), "head": head,
            "dirty_entries": len([x for x in git(["status", "--porcelain=v1", "-z"], root).stdout.split(b"\0") if x]),
            "runs_ignored": git(["check-ignore", "-q", ".agent/runs/probe"], root, check=False).returncode == 0,
            "git_autocrlf": effective_autocrlf(root),
        }
        for name in ("AGENTS.md", "CLAUDE.md"):
            in_head = git(["cat-file", "-e", "HEAD:%s" % name], root, check=False).returncode == 0
            facts["repository"][name] = {"working_tree": (root / name).is_file(), "committed_at_head": in_head}
            if (root / name).is_file() and not in_head:
                notes.append("%s 尚未提交：worktree 基于提交创建，执行器看不到未提交的规则" % name)
        if not facts["repository"]["runs_ignored"]:
            problems.append(".agent/runs/ 未被 .gitignore 忽略")
        notes.extend(planner_file_notes(root, facts["repository"]))
        identity = git_identity_problem(root)
        facts["repository"]["git_identity"] = identity is None
        if identity:
            notes.append(identity)
        facts["pi_context_from_repo_root"] = context_evidence(root, "project")
        notes.extend(facts["pi_context_from_repo_root"]["warnings"])
    except DispatchError as exc:
        notes.append("未在 Git 仓库中运行：%s" % exc)
    facts["problems"] = problems
    facts["notes"] = notes
    facts["ok"] = not problems
    text = json.dumps(redact_obj(facts), ensure_ascii=False, indent=2)
    if out_path is not None:
        out_path.write_text(text + "\n", encoding="utf-8")
    print(text)
    return EXIT_OK if not problems else EXIT_FAIL


def cmd_smoke(args: argparse.Namespace) -> int:
    out_path = safe_output_path(args)
    pi_cmd = resolve_pi_command()
    executor = {"provider": args.provider, "model": args.model, "thinking": args.thinking}
    for field in ("provider", "model"):
        if not MODEL_TOKEN_RE.match(executor[field]):
            raise DispatchError("无效的 %s：%s" % (field, executor[field]), EXIT_USAGE)
    if args.thinking not in FALLBACK_THINKING_LEVELS:
        raise DispatchError("无效的思考级别：%s" % args.thinking, EXIT_USAGE)
    version_text = run_capture(pi_cmd + ["--version"], timeout=60)[1]
    expects_settled = _expects_settled(version_text)
    base_flags = ["--provider", args.provider, "--model", args.model, "--thinking", args.thinking,
                  "--no-session"] + RESOURCE_FLAGS + ["--no-context-files", "--mode", "json"]
    workspace = Path(tempfile.mkdtemp(prefix="pi-smoke-"))
    env, _removed = child_env({})
    steps = [
        ("no_tools", ["--no-tools", "Reply with exactly PI_SMOKE_OK and nothing else."]),
        ("tools", ["--tools", "read,write", "Use the write tool to create a file named smoke.txt whose entire "
                                            "content is PI_TOOL_OK. Then use the read tool to read it back. "
                                            "Finally reply with DONE."]),
    ]
    report: Dict[str, Any] = {"at": utc_now(), "executor": executor, "pi_version": version_text.strip(),
                              "workspace": str(workspace), "steps": []}
    all_ok = True
    for name, extra in steps:
        cmd = pi_cmd + base_flags + extra
        ensure_argv_safe(cmd)
        events_path = workspace / ("%s.events.jsonl" % name)
        stderr_path = workspace / ("%s.stderr.log" % name)
        with open(events_path, "xb") as out, open(stderr_path, "xb") as err:
            result = run_supervised(cmd, workspace, env, out, err, args.timeout)
        summary, final_text = summarize_events(events_path, workspace, executor, stderr_path,
                                               expects_settled=expects_settled)
        ok = result["exit_code"] == 0 and summary["ok"]
        if name == "no_tools":
            ok = ok and "PI_SMOKE_OK" in final_text
        else:
            smoke_file = workspace / "smoke.txt"
            content = smoke_file.read_text(encoding="utf-8").strip() if smoke_file.exists() else None
            ok = ok and content == "PI_TOOL_OK" and summary["tool_errors"] == 0 \
                and summary["tool_calls"].get("write", 0) >= 1 and summary["tool_calls"].get("read", 0) >= 1
        all_ok = all_ok and ok
        report["steps"].append({"name": name, "ok": ok, "exit_code": result["exit_code"],
                                "spawn_error": result["spawn_error"],
                                "wall_seconds": result["wall_seconds"], "timed_out": result["timed_out"],
                                "final_text": redact_secrets(final_text)[:500], "problems": summary["problems"],
                                "actual_models": summary["actual_models"],
                                "provider_thinking_levels": summary["provider_thinking_levels"],
                                "thinking_evidence": summary["thinking_evidence"],
                                "usage": summary["usage"], "cost": summary["cost"]})
        if not ok:
            break
    report["ok"] = all_ok
    text = json.dumps(redact_obj(report), ensure_ascii=False, indent=2)
    if out_path is not None:
        out_path.write_text(text + "\n", encoding="utf-8")
    print(text)
    if all_ok and not args.keep:
        shutil.rmtree(str(workspace), ignore_errors=True)
    return EXIT_OK if all_ok else EXIT_FAIL


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pi_dispatch.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", help="仓库路径（默认当前目录）")
    parser.add_argument("--version", action="version", version="pi_dispatch %s" % TOOL_VERSION)
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("doctor", help="环境核验，不调用模型")
    p.add_argument("--provider")
    p.add_argument("--model")
    p.add_argument("--thinking")
    p.add_argument("--out", help="同时写入 JSON 文件（仅限 .agent/runs/_env/ 或 _reports/）")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("smoke", help="最小连通性试跑（会调用模型并产生费用）")
    p.add_argument("--provider", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--thinking", default=DEFAULT_THINKING)
    p.add_argument("--timeout", type=int, default=300)
    p.add_argument("--out")
    p.add_argument("--keep", action="store_true", help="保留临时目录")
    p.set_defaults(func=cmd_smoke)

    p = sub.add_parser("validate", help="校验 .agent/plans/<plan-key>.md 与 .json")
    p.add_argument("plan_key", help="task-id.vN，或 .agent/plans/ 下合同文件的路径")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("derive-json", help="由 Markdown 合同生成机器合同 JSON 并校验")
    p.add_argument("plan_key", help="task-id.vN，或 .agent/plans/ 下合同文件的路径")
    p.add_argument("--title", help="合同标题（缺省取 Goal 的第一行）")
    p.add_argument("--force", action="store_true", help="覆盖已存在的 JSON")
    p.add_argument("--print", dest="print_only", action="store_true", help="只打印，不写文件")
    p.set_defaults(func=cmd_derive_json)

    p = sub.add_parser("baseline", help="在基线上运行合同检查，确认探针能区分修复前后（不创建 attempt）")
    p.add_argument("plan_key", help="task-id.vN，或 .agent/plans/ 下合同文件的路径")
    p.add_argument("--only", help="只运行指定检查，逗号分隔")
    p.add_argument("--keep-workspace", action="store_true", help="保留基线副本，便于排查")
    p.set_defaults(func=cmd_baseline)

    p = sub.add_parser("prepare", help="创建 attempt 与独立 worktree")
    p.add_argument("plan_key", help="task-id.vN，或 .agent/plans/ 下合同文件的路径")
    p.set_defaults(func=cmd_prepare)

    p = sub.add_parser("run", help="运行 Pi 并收集证据（耗时长，请在后台运行）")
    p.add_argument("run_dir")
    p.add_argument("--timeout", type=int, help="进一步收紧本轮时限（秒），不能超过合同预算")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("collect", help="调度器异常退出后恢复证据收集")
    p.add_argument("run_dir")
    p.add_argument("--recover", action="store_true")
    p.set_defaults(func=cmd_collect)

    p = sub.add_parser("check", help="在固定候选上运行合同检查")
    p.add_argument("run_dir")
    p.add_argument("--only", help="只运行指定检查，逗号分隔（不能作为 PASS 依据）")
    p.add_argument("--fresh", action="store_true", help="在干净副本（基线 + 候选补丁 + setup）上运行")
    p.add_argument("--keep-workspace", action="store_true", help="--fresh 时保留干净副本，便于排查")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("mutate", help="在干净副本上逐个套用最小变异，检查测试能否抓住")
    p.add_argument("run_dir")
    p.add_argument("--spec", required=True, help="变异清单 JSON（格式见 review-pi/mutation-check.md）")
    p.add_argument("--keep-workspace", action="store_true", help="保留干净副本，便于排查")
    p.set_defaults(func=cmd_mutate)

    p = sub.add_parser("wait", help="等待运行中的 attempt 结束（给没有完成通知的规划端轮询）")
    p.add_argument("run_dir")
    p.add_argument("--timeout", type=int, default=540, help="最多等待的秒数（默认 540；到时仍在运行时退出码 3）")
    p.add_argument("--interval", type=float, default=5.0, help=argparse.SUPPRESS)
    p.set_defaults(func=cmd_wait)

    p = sub.add_parser("sync-adapters", help="把 .agents/skills 中的技能复制到 .claude/skills（Claude Code 适配）")
    p.add_argument("--check", action="store_true", help="只检查是否一致，不写文件；不一致时退出码 1")
    p.set_defaults(func=cmd_sync_adapters)

    p = sub.add_parser("verdict", help="执行门禁并记录验收结论")
    p.add_argument("run_dir")
    p.add_argument("--verdict", required=True, choices=VERDICTS)
    p.add_argument("--review", required=True, help="复审报告路径（含 'Verdict: X' 行）")
    p.add_argument("--class", dest="failure_class", choices=FAILURE_CLASSES)
    p.add_argument("--waive", action="append", help="G2=原因（仅 ACCEPTED_WITH_EXCEPTION）")
    p.add_argument("--decided-by")
    p.add_argument("--human-minutes", type=float)
    p.add_argument("--note")
    p.set_defaults(func=cmd_verdict)

    p = sub.add_parser("status", help="列出 attempt")
    p.add_argument("task_id", nargs="?", help="task-id（列出全部）、task-id.vN、task-id/attempt-NNN 或 attempt 路径")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("metrics", help="汇总试运行指标")
    p.add_argument("--out")
    p.set_defaults(func=cmd_metrics)

    p = sub.add_parser("branch", help="为候选创建本地分支（不推送）")
    p.add_argument("run_dir")
    p.add_argument("--name")
    p.add_argument("--rework", action="store_true", help="为 REVISE 的候选建返工基线")
    p.add_argument("--trailer", action="append", default=[],
                   help="追加一条提交尾注（单行 Key: value，可重复），例如本次规划端的署名")
    p.add_argument("--no-config-trailers", action="store_true",
                   help="不附加 dispatch.config.json 的 commit_trailers（它们是仓库级的固定尾注）")
    p.set_defaults(func=cmd_branch)

    p = sub.add_parser("mark", help="标记 INTEGRATED / ABANDONED / SUPERSEDED")
    p.add_argument("run_dir")
    p.add_argument("state", choices=("INTEGRATED", "ABANDONED", "SUPERSEDED"))
    p.add_argument("--ref")
    p.add_argument("--reason")
    p.add_argument("--force", action="store_true", help="放弃停在 RUNNING/COLLECTING/PREPARING 的 attempt")
    p.set_defaults(func=cmd_mark)

    p = sub.add_parser("cleanup", help="移除 attempt 的 worktree，保留证据")
    p.add_argument("run_dir")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_cleanup)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return EXIT_USAGE
    try:
        return int(args.func(args))
    except DispatchError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return exc.code
    except KeyboardInterrupt:
        print("已取消。", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
