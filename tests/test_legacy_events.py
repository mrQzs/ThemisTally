#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P4 旧行为特征化回归：Pi 预检、事件完整性、实际模型与思考级别证据、用量与费用（01-A07；C.4“实际模型与思考级别证据”）。

锁定对象：提交 a4fa199b0e5bdc658215765ee7558b9fe6723940 的 scripts/pi_dispatch.py（TOOL_VERSION 2.2.2）。
这是特征化测试：断言旧实现的**现状**，不修 bug。现状可疑之处在各测试 docstring 中标注，并引用
docs/code-kit-v2/01-baseline/legacy-inventory.md 的条目号（LB-*）或 compatibility-matrix.md 的 D 编号。
源码行号均指该提交中的 scripts/pi_dispatch.py。

两类用例
--------
- 端到端（黑盒）：tests/legacy_harness.py 建临时仓库与受控环境，make_fake_pi 生成假 pi，经
  ``python scripts/pi_dispatch.py prepare/run/check/verdict/status/doctor`` 驱动，断言退出码、stdout/stderr
  片段、state.json、events-summary.json、summary.md 等落盘证据。
- 进程内（白盒）：用 load_legacy_module 加载同一份 pi_dispatch.py 字节，直接调用 ``summarize_events``
  （处理本文件构造的事件文件）、``pi_preflight``（仍以子进程运行假 pi）或 ``_expects_settled``。
  这些断言依赖内部函数签名，只说明函数层面的现状；各测试 docstring 标“白盒”。

运行：``PYTHONDONTWRITEBYTECODE=1 python tests/test_legacy_events.py``（按 01-L04 单独运行，不用 discover）。
不调用真实 pi/claude/codex、不联网：子进程环境由 legacy_harness 隔离（01-L05），假 pi 只在用例临时区域内。

平台：本机实测 Windows Server 2025 + Python 3.12.10。本文件没有平台专属用例；假 pi 的事件行在 Windows 上
默认是 CRLF（与 tests/stub_pi.py 相同），进程内用例按需写 LF 或 CRLF。Linux/macOS 未运行（NOT_RUN）。

本文件没有覆盖的相关旧行为（legacy-inventory 4.14、11.5 第 6、7 条）：
- LB-EVENTS-026 的另两类异常输入（非字符串 text、含 NUL 的工具路径）与端到端后果（run 停在 COLLECTING、
  wait 持续返回 3）；
- entry_appended 与 message_end 重复计同一次调用的端到端形态、auto_retry 记录、Infinity/NaN 写出；
- 预检第 1 步“摘要优先取 stderr”、第 7 步“摘要优先取 stdout”的取舍（假 pi 的 --help 与 auth 模式不写 stderr，
  本文件只锁定 stderr 为空时的文本）；第 7 步 help 中没有 `pi auth` 时的 note；预检的 run_capture 超时与找不到程序；
- context_evidence（LB-EVENTS-004）、resolve_pi_command 的 which 与 .cmd 分支、ensure_argv_safe（LB-EVENTS-002/003）；
- smoke（会按 FALLBACK 列表拒绝思考级别，LB-EVENTS-027）、_live_progress（LB-EVENTS-029）、脱敏（LB-EVENTS-022/023）；
- 取消与超时对事件摘要的影响（属于 LB-LIFE，另有文件负责）。

变异核对（开发时做过，未固化为测试）：在临时副本中对 pi_dispatch.py 做单点改动，用 CODEKIT_LEGACY_KIT_DIR
指向副本运行本文件。首轮 16 处（例如 bool 不计入用量、responseModel 参与比较、G1 放过退出码 5、截断判定恒为
False、按对象去重 message_end、doctor 思考级别改为 note）；复审后补了 10 处：compaction 不再使费用为 partial
（:2336）、doctor 改按 FALLBACK 列表判定思考级别（:4725）、忽略 --help 退出码（:2023）、忽略 auth check 失败
（:2061）、WORK_EVENTS 只剩 turn_start（:2078）、settled 之后的 agent_end(willRetry=false) 也清除待完成工作
（:2297）、summarize_events 默认读取同目录的 stderr.log（:2330）、list-models 失败摘要改为优先取 stdout
（:2052）、预检的 auth check 加 --no-refresh（:2058）、willRetry 不再转 bool（:2296）。每一处都至少让本文件一个
对应用例失败（SourceFactsTests 在副本中按设计失败，不计入）。
"""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

sys.dont_write_bytecode = True
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))

from legacy_harness import (  # noqa: E402
    DEFAULT_USAGE, OK_FILES, LegacyCase, assistant_message, legacy_facts, ok_events, stub_pi_path,
)

# ---------------------------------------------------------------------------
# 旧实现的固定文本（逐字取自 scripts/pi_dispatch.py@a4fa199）
# ---------------------------------------------------------------------------

REQUESTED = "step/step-5-preview"
PREFLIGHT_ERROR = "ERROR: 预检失败：attempt 保持 PREPARED，未计入尝试次数。修正环境后可再次 run。"  # :3285、:4967
NO_TERMINAL = "没有观察到完整的结束事件（agent_settled / agent_end）"  # :2349
NO_SETTLED = "没有 agent_settled：该 pi 版本应以它结束，事件流可能被截断或运行被中断"  # :2347
EMPTY_STREAM = "事件流为空"  # :2340
TRUNCATED = "事件流最后一行不完整（可能被截断）"  # :2344
MODEL_NOT_LISTED = ("模型 step/step-5-preview 不在本机可用模型列表中（可能是拼写错误、缺少凭据或未在 models.json 定义；"
                    "Pi 对未知模型可能只警告并按自定义 ID 发送）")  # :2054-2055
ZERO_USAGE = {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0, "totalTokens": 0}
STUB_THINKING_LINE = "Set thinking level: off, minimal, low, medium, high, xhigh, max"
STUB_BASH_TOOL_LINE = "  bash       - Execute bash commands\n"
EXECUTOR = {"provider": "step", "model": "step-5-preview", "thinking": "high",
            "tools": ["read", "grep", "find", "ls", "edit", "write", "bash"], "context_files": "project"}

EventLine = Union[Dict[str, Any], str, bytes]


def stub_help() -> str:
    """tests/stub_pi_help.txt 的文本（与 stub 相同的 --help 输出，能通过预检）。"""
    return (stub_pi_path().parent / "stub_pi_help.txt").read_text(encoding="utf-8")


def replaced(text: str, old: str, new: str) -> str:
    """替换且必须恰好命中一次，避免 help 样本变化后测试静默失效。"""
    if text.count(old) != 1:
        raise AssertionError("help 样本中 %r 出现 %d 次，应为 1 次" % (old, text.count(old)))
    return text.replace(old, new)


def final_message_index(events: Sequence[Dict[str, Any]]) -> int:
    """ok_events 中最后一条 assistant message_end 的下标。"""
    for index in range(len(events) - 1, -1, -1):
        event = events[index]
        if event.get("type") == "message_end" and (event.get("message") or {}).get("role") == "assistant":
            return index
    raise AssertionError("事件序列中没有 assistant message_end")


def assistant(text: str = "done", stop: str = "stop", usage: Optional[Dict[str, Any]] = None,
              **extra: Any) -> Dict[str, Any]:
    """进程内用例使用的 assistant message_end 事件（provider/model 与 EXECUTOR 一致）。"""
    message = assistant_message([{"type": "text", "text": text}], stop, provider="step", model="step-5-preview",
                                usage=usage if usage is not None else DEFAULT_USAGE, extra=extra or None)
    return {"type": "message_end", "message": message}


class EventsCase(LegacyCase):
    """本文件的公共辅助：端到端运行假 pi，以及进程内调用 summarize_events / pi_preflight。"""

    # -- 端到端 -----------------------------------------------------------------

    def prepared_repo(self, name: str) -> Path:
        repo, _base = self.make_repo(name)
        code, out = self.tool(repo, "prepare", "normalize-query.v1")
        self.assertEqual(code, 0, "prepare 失败：\n" + out)
        self.assertEqual(self.state(repo), "PREPARED")
        return repo

    def run_fake(self, repo: Path, events: Sequence[EventLine], exit_code: int = 0,
                 **kwargs: Any) -> Tuple[int, str, str]:
        """用假 pi 运行 attempt-001，返回 (退出码, stdout, stderr)。默认写入 stub ok 场景的两个文件。"""
        kwargs.setdefault("files", OK_FILES)
        pi = self.fake_pi(list(events), exit_code, **kwargs)
        return self.tool_split(repo, "run", self.attempt_ref(1), pi_cmd=pi)

    def events_summary(self, repo: Path) -> Dict[str, Any]:
        return self.jload(self.rd(repo) / "events-summary.json")

    def summary_md(self, repo: Path) -> str:
        return (self.rd(repo) / "summary.md").read_text(encoding="utf-8")

    def history(self, repo: Path) -> List[Dict[str, Any]]:
        text = (self.rd(repo) / "history.jsonl").read_text(encoding="utf-8")
        return [json.loads(line) for line in text.splitlines() if line.strip()]

    def argv_calls(self, log: Path) -> List[Dict[str, Any]]:
        """假 pi 的 argv_log：每次调用一条 {"mode", "argv", "cwd"}（argv 不含解释器与脚本路径）。"""
        return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]

    def argv_modes(self, log: Path) -> List[str]:
        return [call["mode"] for call in self.argv_calls(log)]

    def assert_preflight_blocked(self, repo: Path, code: int, out: str, err: str, problems: List[str]) -> None:
        """预检失败在 run 中的旧表现（LB-EVENTS-008，:3281-3285）：退出 3，逐条 PREFLIGHT，attempt 保持未领取的 PREPARED。"""
        self.assertEqual(code, self.pd.EXIT_BLOCKED, out + err)
        self.assertEqual(code, 3)
        self.assertEqual([line[len("PREFLIGHT "):] for line in out.splitlines() if line.startswith("PREFLIGHT ")],
                         problems, out)
        self.assertIn(PREFLIGHT_ERROR, err)
        rd = self.rd(repo)
        self.assertEqual(self.state(repo), "PREPARED")
        for absent in ("claim", "run-started.json", "run.json", "events.jsonl", "executor.json"):
            self.assertFalse((rd / absent).exists(), absent)
        preflight = self.jload(rd / "preflight" / "preflight.json")
        self.assertEqual((preflight["ok"], preflight["problems"]), (False, problems))
        self.assertTrue((rd / "preflight" / "context-files.json").is_file(), "context-files.json 无条件写出（:3280）")
        last = self.history(repo)[-1]
        self.assertEqual((last.get("event"), last.get("problems")), ("preflight_failed", problems))

    # -- 进程内（白盒） -----------------------------------------------------------

    def summarize(self, lines: Sequence[EventLine], *, expects_settled: Optional[bool] = True, eol: str = "\n",
                  stderr_text: Optional[Union[str, bytes]] = None, stderr_arg: str = "written",
                  executor: Optional[Dict[str, Any]] = None) -> Tuple[Dict[str, Any], str]:
        """把事件写成文件后调用 pd.summarize_events（白盒）。

        dict → json.dumps 加 eol；str → 原样加 eol；bytes → 原样写出、不加行尾。{{provider}}/{{model}}/{{thinking}}/{{cwd}}
        按 make_fake_pi 的规则替换为 EXECUTOR 的值与工作目录。stderr_text 不为 None 时在 events.jsonl 同目录写
        stderr.log（str 按 UTF-8，bytes 原样）。stderr_arg 决定传给 stderr_path 的值："written"（默认）传刚写的
        stderr.log（没写时传 None）；"none" 传 None（文件照写）；"missing" 传同目录下不存在的 stderr-missing.log。
        本次的目录记在 self.inproc_dir（其中有 events.jsonl、stderr.log 与工作目录 wt/）。
        """
        if stderr_arg not in ("written", "none", "missing"):
            raise ValueError("stderr_arg 必须是 written、none 或 missing")
        self._inproc = getattr(self, "_inproc", 0) + 1
        base = self.work / ("inproc-%02d" % self._inproc)
        self.inproc_dir = base
        work_dir = base / "wt"
        work_dir.mkdir(parents=True)
        subs = {"{{provider}}": "step", "{{model}}": "step-5-preview", "{{thinking}}": "high",
                "{{cwd}}": json.dumps(str(work_dir))[1:-1]}
        data = bytearray()
        for item in lines:
            if isinstance(item, bytes):
                data += item
                continue
            text = item if isinstance(item, str) else json.dumps(item)
            for key, value in subs.items():
                text = text.replace(key, value)
            data += (text + eol).encode("utf-8")
        events_path = base / "events.jsonl"
        events_path.write_bytes(bytes(data))
        stderr_path: Optional[Path] = None
        if stderr_text is not None:
            stderr_path = base / "stderr.log"
            stderr_path.write_bytes(stderr_text if isinstance(stderr_text, bytes) else stderr_text.encode("utf-8"))
        if stderr_arg == "none":
            stderr_path = None
        elif stderr_arg == "missing":
            stderr_path = base / "stderr-missing.log"
            self.assertFalse(stderr_path.exists())
        return self.pd.summarize_events(events_path, work_dir, dict(executor or EXECUTOR), stderr_path,
                                        expects_settled=expects_settled)

    def preflight(self, *, executor: Optional[Dict[str, Any]] = None, **fake_kwargs: Any) -> Dict[str, Any]:
        """白盒：pd.pi_preflight 对假 pi 的结果（假 pi 仍是子进程，环境为受控环境）。

        产物目录记在 self.preflight_dir（pi-help.txt、pi-version.txt、list-models.txt、auth-check.json、preflight.json）。
        """
        pi = self.fake_pi([], 0, **fake_kwargs)
        self._pf = getattr(self, "_pf", 0) + 1
        out_dir = self.work / ("preflight-%02d" % self._pf)
        self.preflight_dir = out_dir
        result = self.pd.pi_preflight(pi, self.work, dict(executor or EXECUTOR), out_dir, self.child_env(pi_cmd=pi))
        self.assertEqual(self.jload(out_dir / "preflight.json")["problems"], result["problems"])
        return result


# ---------------------------------------------------------------------------
# 预检（LB-EVENTS-001、005–008、027）
# ---------------------------------------------------------------------------

class PreflightRunTests(EventsCase):
    """端到端：run 中的预检分支。旧测试只覆盖“模型未列出”“auth 未就绪”且只断言非 0（legacy-inventory 4.14、10 节）。"""

    def test_LB_EVENTS_007_thinking_not_in_help_list_blocks_run(self):
        """LB-EVENTS-007（预检第 3 步，:2031-2033）、LB-EVENTS-008（:3281-3285）。
        验收：01-A07；C.4“实际模型与思考级别证据”缺口“预检的思考级别不在列表（:2032）”。

        help 的 thinking 行只列到 medium 时，请求 high 被预检拒绝：退出 3，attempt 保持 PREPARED，
        假 pi 只被调用 help/version/list-models/auth 四次，没有进入运行模式。
        同时锁定四次调用的参数（legacy-inventory 4.2 第 1、5、6、7 步与 4.11“凭据”行）：help 与 list-models 带
        RESOURCE_FLAGS；--version 不带；auth check 为 `auth check --provider P --model M --json`，
        **不带** --no-refresh（doctor 才带），也不带 RESOURCE_FLAGS。
        """
        repo = self.prepared_repo("pf-thinking")
        log = self.work / "argv.jsonl"
        help_text = replaced(stub_help(), STUB_THINKING_LINE, "Set thinking level: off, minimal, low, medium")
        code, out, err = self.run_fake(repo, ok_events(), help_text=help_text, argv_log=log)
        problem = ("思考级别 high 不在本机 pi 支持列表 ['off', 'minimal', 'low', 'medium'] 中"
                   "（Pi 对无效值只警告并忽略）")
        self.assert_preflight_blocked(repo, code, out, err, [problem])
        preflight = self.jload(self.rd(repo) / "preflight" / "preflight.json")
        self.assertEqual(preflight["help"]["thinking_levels"], ["off", "minimal", "low", "medium"])
        self.assertEqual(self.argv_modes(log), ["help", "version", "list-models", "auth"])
        argvs = {call["mode"]: call["argv"] for call in self.argv_calls(log)}
        resource_flags = list(self.pd.RESOURCE_FLAGS)
        self.assertEqual(resource_flags, ["--no-approve", "--no-extensions", "--no-skills", "--no-prompt-templates",
                                          "--no-themes"])
        self.assertEqual(argvs["help"], resource_flags + ["--help"])
        self.assertEqual(argvs["version"], ["--version"])
        self.assertEqual(argvs["list-models"], resource_flags + ["--list-models", "step-5-preview"])
        self.assertEqual(argvs["auth"], ["auth", "check", "--provider", "step", "--model", "step-5-preview", "--json"])
        self.assertNotIn("--no-refresh", argvs["auth"])

    def test_LB_EVENTS_007_unknown_builtin_tool_blocks_run(self):
        """LB-EVENTS-007（预检第 4 步，:2034-2037）、LB-EVENTS-008。
        验收：01-A07；C.4“实际模型与思考级别证据”缺口“未知工具（:2037）”。

        help 的 Built-in Tool Names 一节缺 bash，而合同 tools 含 bash：预检只报这一条，退出 3。
        """
        repo = self.prepared_repo("pf-tool")
        help_text = replaced(stub_help(), STUB_BASH_TOOL_LINE, "")
        code, out, err = self.run_fake(repo, ok_events(), help_text=help_text)
        self.assert_preflight_blocked(repo, code, out, err,
                                      ["本机 pi 没有这些内置工具：bash（Pi 会静默忽略未知工具名）"])
        preflight = self.jload(self.rd(repo) / "preflight" / "preflight.json")
        self.assertNotIn("bash", preflight["help"]["builtin_tools"])
        self.assertIn("powershell", preflight["help"]["builtin_tools"])

    def test_LB_EVENTS_007_two_part_version_is_unreadable(self):
        """LB-EVENTS-001（parse_version 只认三段版本，:373-375）、LB-EVENTS-007（预检第 5 步，:2038-2043）、LB-EVENTS-008。
        验收：01-A07；C.4“实际模型与思考级别证据”缺口“版本不可读（:2043）”。

        --version 输出“0.87”（两段）时 parse_version 解析不出，预检报“无法读取 pi 版本：0.87”，退出 3。
        """
        repo = self.prepared_repo("pf-version")
        code, out, err = self.run_fake(repo, ok_events(), version="0.87")
        self.assert_preflight_blocked(repo, code, out, err, ["无法读取 pi 版本：0.87"])
        self.assertEqual((self.rd(repo) / "preflight" / "pi-version.txt").read_text(encoding="utf-8"), "0.87\n")

    def test_LB_EVENTS_007_list_models_failure_blocks_run(self):
        """LB-EVENTS-007（预检第 6 步，:2047-2052）、LB-EVENTS-008。
        验收：01-A07；C.4“实际模型与思考级别证据”缺口“list-models 失败”。

        --list-models 退出码非 0、stdout 与 stderr 都有内容时：problem 取 **stderr**（`(err or out)`，strip 后脱敏、
        截前 300 个字符；本例 stderr 有 512 个字符）；list-models.txt 记 **stdout 在前、stderr 在后**的拼接；退出 3。
        """
        repo = self.prepared_repo("pf-listmodels")
        stdout_text = "partial table on stdout\n"
        long_err = "Error: cannot load model catalog " + " ".join("line%03d" % i for i in range(60))
        self.assertEqual(len(long_err), 512)
        code, out, err = self.run_fake(repo, ok_events(), list_models_exit_code=2, list_models_output=stdout_text,
                                       list_models_stderr=long_err + "\n")
        problem = "pi --list-models 失败：" + long_err[:300]
        self.assertTrue(problem.endswith(" line032 lin"), problem[-20:])  # 按字符截断，不按词
        self.assert_preflight_blocked(repo, code, out, err, [problem])
        listed = (self.rd(repo) / "preflight" / "list-models.txt").read_text(encoding="utf-8")
        self.assertEqual(listed, stdout_text + long_err + "\n")

    def test_LB_EVENTS_007_auth_not_ready_blocks_run(self):
        """LB-EVENTS-007（预检第 7 步，:2056-2062）、LB-EVENTS-008。
        验收：01-A07；C.4“实际模型与思考级别证据”（凭据就绪）。旧测试 test_dispatch.py:502 只断言非 0 且输出含 "auth"。

        auth check 退出 1（假 pi 输出 {"status": "not_ready", …}）：problem 为完整的
        “pi auth check 未就绪（退出码 1）：<stdout 去首尾空白>”；auth-check.json 写 stdout；run 退出 3，保持 PREPARED。
        """
        repo = self.prepared_repo("pf-auth")
        log = self.work / "argv.jsonl"
        code, out, err = self.run_fake(repo, ok_events(), auth_status="not_ready", argv_log=log)
        auth_json = {"status": "not_ready", "provider": "step", "model": "step-5-preview"}
        self.assert_preflight_blocked(repo, code, out, err,
                                      ["pi auth check 未就绪（退出码 1）：" + json.dumps(auth_json)])
        self.assertEqual(self.jload(self.rd(repo) / "preflight" / "auth-check.json"), auth_json)
        self.assertEqual(self.argv_modes(log), ["help", "version", "list-models", "auth"])

    def test_LB_EVENTS_001_low_version_is_note_and_agent_end_completes(self):
        """LB-EVENTS-001（MIN_PI_VERSION=(0,80,4)，:50、:2044-2046、:3288、:3316）、LB-EVENTS-011（:2312-2315）。
        验收：01-A07；C.4“实际模型与思考级别证据”缺口“低于 0.80.4（:2045）”。

        版本 0.80.3 低于 MIN_PI_VERSION 只记 note、不阻止运行；run-started.json/run.json 写
        expects_agent_settled=false，于是没有 agent_settled、以 agent_end(willRetry=false) 结束的流判为完整，run 退出 0。
        可疑点：“0.80.4 起提供 agent_settled”只有源码注释这一来源（legacy-inventory 4.15）。
        """
        repo = self.prepared_repo("pf-lowversion")
        code, out, err = self.run_fake(repo, ok_events(settled=False), version="0.80.3")
        note = "pi 0.80.3 低于 0.80.4，缺少 agent_settled 事件；将退回用 agent_end 判断结束"
        self.assertEqual(code, 0, out + err)
        self.assertIn("NOTE  " + note, out.splitlines())
        rd = self.rd(repo)
        preflight = self.jload(rd / "preflight" / "preflight.json")
        self.assertEqual((preflight["ok"], preflight["problems"]), (True, []))
        self.assertIn(note, preflight["notes"])
        self.assertIs(self.jload(rd / "run-started.json")["expects_agent_settled"], False)
        self.assertIs(self.jload(rd / "run.json")["expects_agent_settled"], False)
        ev = self.events_summary(repo)
        self.assertEqual((ev["terminal_event"], ev["complete"], ev["ok"], ev["problems"]),
                         ("agent_end", True, True, []))
        self.assertNotIn("agent_settled", ev["event_counts"])
        self.assertEqual(self.state(repo), "NEEDS_REVIEW")


class PreflightWhiteBoxTests(EventsCase):
    """白盒：直接调用 pd.pi_preflight / pd._expects_settled（假 pi 仍以子进程运行）。"""

    def test_LB_EVENTS_001_expects_settled_from_version_text(self):
        """LB-EVENTS-001（:50、:373-375、:3245-3247）。白盒。验收：01-A07。

        _expects_settled：取文本中第一个“数字.数字.数字”；解析不出为 None，≥0.80.4 为 True，其余 False。
        """
        pd = self.pd
        self.assertEqual(pd.MIN_PI_VERSION, (0, 80, 4))
        cases = {"0.80.4": True, "0.80.3": False, "0.87.0\n": True, "pi version 1.2.3-beta": True,
                 "0.87": None, "": None, "v0.79.9 (build 0.99.0)": False}
        for text, expected in cases.items():
            self.assertIs(pd._expects_settled(text), expected, text)

    def test_LB_EVENTS_007_version_problem_variants(self):
        """LB-EVENTS-007（预检第 5 步，:2038-2046）。白盒。验收：01-A07；C.4“实际模型与思考级别证据”（版本分支）。

        - 不输出版本：problem 为“无法读取 pi 版本：”（冒号后为空），pi-version.txt 只有换行；
        - 输出 0.87.0 但退出码 1：同样报“无法读取 pi 版本：0.87.0”（退出码与解析失败共用一条），pi-version.txt 照写版本；
        - 0.80.3：ok=true，只有 note；0.80.4：没有版本 note。
        """
        result = self.preflight(version=None)
        self.assertEqual((result["ok"], result["problems"], result["pi_version"]),
                         (False, ["无法读取 pi 版本："], ""))
        self.assertEqual((self.preflight_dir / "pi-version.txt").read_text(encoding="utf-8"), "\n")
        result = self.preflight(version="0.87.0", version_exit_code=1)
        self.assertEqual((result["ok"], result["problems"]), (False, ["无法读取 pi 版本：0.87.0"]))
        self.assertEqual((self.preflight_dir / "pi-version.txt").read_text(encoding="utf-8"), "0.87.0\n")
        result = self.preflight(version="0.80.3")
        self.assertEqual((result["ok"], result["problems"]), (True, []))
        self.assertEqual(result["notes"], ["pi 0.80.3 低于 0.80.4，缺少 agent_settled 事件；将退回用 agent_end 判断结束"])
        result = self.preflight(version="0.80.4")
        self.assertEqual((result["ok"], result["problems"], result["notes"]), (True, [], []))

    def test_LB_EVENTS_005_help_parse_fallbacks_skip_checks(self):
        """LB-EVENTS-005（parse_help，:1860-1871）、LB-EVENTS-007（第 3、4 步）。白盒。
        验收：01-A07；C.4“实际模型与思考级别证据”。

        - help 中匹配不到“--thinking <level> …: a, b”一行时，静默退回固定列表 off…max，请求 high 通过；
        - help 没有“Built-in Tool Names:”一节时跳过工具核对，未知工具名 nosuch 也不报。
        可疑点：两处退回都不留 note，预检通过不代表本机 pi 支持该级别或工具（legacy-inventory 4.2）。
        """
        no_list = replaced(stub_help(), STUB_THINKING_LINE, "Set thinking level")
        result = self.preflight(help_text=no_list)
        self.assertEqual((result["ok"], result["problems"]), (True, []))
        self.assertEqual(result["help"]["thinking_levels"], list(self.pd.FALLBACK_THINKING_LEVELS))
        self.assertEqual(result["help"]["thinking_levels"], ["off", "minimal", "low", "medium", "high", "xhigh", "max"])
        help_text = stub_help()
        no_tools = help_text[:help_text.index("Built-in Tool Names:")]
        executor = dict(EXECUTOR, tools=["read", "nosuch"])
        result = self.preflight(help_text=no_tools, executor=executor)
        self.assertEqual((result["ok"], result["problems"], result["help"]["builtin_tools"]), (True, [], []))

    def test_LB_EVENTS_007_missing_required_flags(self):
        """LB-EVENTS-007（预检第 2 步，:2025-2030；REQUIRED_PI_FLAGS :69-70）。白盒。
        验收：01-A07；C.4“实际模型与思考级别证据”缺口“不支持的参数”。

        - help 缺 --no-themes：problem“本机 pi 不支持参数：--no-themes”；
        - help 缺 --no-context-files：context_files=project 时不要求（ok），context_files=none 时报缺失。
        """
        no_themes = replaced(stub_help(), "  --no-themes                    Disable theme discovery and loading\n", "")
        result = self.preflight(help_text=no_themes)
        self.assertEqual((result["ok"], result["problems"]), (False, ["本机 pi 不支持参数：--no-themes"]))
        no_ctx = replaced(stub_help(),
                          "  --no-context-files, -nc        Disable AGENTS.md and CLAUDE.md discovery and loading\n", "")
        result = self.preflight(help_text=no_ctx)
        self.assertEqual((result["ok"], result["problems"]), (True, []))
        result = self.preflight(help_text=no_ctx, executor=dict(EXECUTOR, context_files="none"))
        self.assertEqual((result["ok"], result["problems"]), (False, ["本机 pi 不支持参数：--no-context-files"]))

    def test_LB_EVENTS_007_help_nonzero_exit_is_problem(self):
        """LB-EVENTS-007（预检第 1 步，:2020-2024）。白盒。验收：01-A07；C.4“实际模型与思考级别证据”（预检）。

        --help 退出码 1、stderr 为空而 stdout 是完整 help：problem 为“pi --help 退出码 1：”加 stdout 去首尾空白后的
        前 300 个字符（脱敏不改变这段文字）；help 仍被解析，其余步骤都通过，所以只有这一条 problem。
        假 pi 用 LF 行尾（同真实 pi），使摘要与平台无关。
        """
        help_text = stub_help()
        result = self.preflight(help_exit_code=1, line_ending="lf")
        problem = "pi --help 退出码 1：" + help_text.strip()[:300]
        self.assertEqual((result["ok"], result["problems"]), (False, [problem]))
        self.assertTrue(result["problems"][0].startswith("pi --help 退出码 1：pi - AI coding assistant"))
        self.assertIn("powershell", result["help"]["builtin_tools"])  # 退出码非 0 也照常解析 help

    def test_LB_EVENTS_007_no_models_and_no_match_share_one_problem(self):
        """LB-EVENTS-005/007（预检第 6 步，:1874-1886、:2047-2055）。白盒。验收：01-A07；C.4“实际模型与思考级别证据”。

        预检不区分三种情形：没有任何模型（No models available）、没有匹配（No models matching）、
        同名模型挂在别的 provider 下（表格中有 other/step-5-preview）。三者给出同一条 problem（doctor 才区分）。
        """
        for models in ((), (("other", "other-model"),), (("other", "step-5-preview"),)):
            result = self.preflight(models=models)
            self.assertEqual((result["ok"], result["problems"]), (False, [MODEL_NOT_LISTED]), models)


class DoctorThinkingTests(EventsCase):

    def test_LB_EVENTS_027_doctor_rejects_unsupported_thinking(self):
        """LB-EVENTS-027（doctor 的思考级别检查，:4725-4726；输出与退出码 :4758-4762）。
        验收：01-A07；C.4“实际模型与思考级别证据”缺口“doctor 的思考级别检查（:4726）”。

        doctor --provider/--model/--thinking ultra：只多一条 problem“思考级别 ultra 不受本机 pi 支持”，
        退出 1（EXIT_FAIL）；模型已列出、凭据就绪（auth check 带 --no-refresh）。
        """
        repo, _base = self.make_repo("doctor")
        log = self.work / "argv.jsonl"
        pi = self.fake_pi([], 0, argv_log=log)
        code, out, err = self.tool_split(repo, "doctor", "--provider", "step", "--model", "step-5-preview",
                                         "--thinking", "ultra", pi_cmd=pi)
        self.assertEqual(code, self.pd.EXIT_FAIL, out + err)
        facts = json.loads(out)
        self.assertEqual(facts["problems"], ["思考级别 ultra 不受本机 pi 支持"])
        self.assertIs(facts["ok"], False)
        self.assertIs(facts["executor_model_listed"], True)
        auth_calls = [json.loads(line)["argv"] for line in log.read_text(encoding="utf-8").splitlines()
                      if json.loads(line)["mode"] == "auth"]
        self.assertEqual(len(auth_calls), 1)
        self.assertIn("--no-refresh", auth_calls[0])

    def test_LB_EVENTS_027_doctor_thinking_uses_help_list(self):
        """LB-EVENTS-027（doctor 的思考级别检查，:4725-4726；legacy-inventory 4.11“思考级别”行）。
        验收：01-A07；C.4“实际模型与思考级别证据”缺口“doctor 的思考级别检查（:4726）”。

        doctor 按本机 help 解析出的列表判定，不按 FALLBACK 固定列表（smoke 才按固定列表）：
        - help 的 thinking 行只到 medium，--thinking high（在固定列表中）：报“思考级别 high 不受本机 pi 支持”，退出 1；
        - help 的 thinking 行多出自定义级别 ultra（不在固定列表中），--thinking ultra：不报这一条，ok=true，退出 0。
        """
        self.assertIn("high", self.pd.FALLBACK_THINKING_LEVELS)
        self.assertNotIn("ultra", self.pd.FALLBACK_THINKING_LEVELS)
        repo, _base = self.make_repo("doctor-help-list")
        cases = (("Set thinking level: off, minimal, low, medium", "high",
                  ["off", "minimal", "low", "medium"], ["思考级别 high 不受本机 pi 支持"], self.pd.EXIT_FAIL),
                 ("Set thinking level: off, minimal, low, medium, high, xhigh, max, ultra", "ultra",
                  ["off", "minimal", "low", "medium", "high", "xhigh", "max", "ultra"], [], self.pd.EXIT_OK))
        for line, level, levels, problems, exit_code in cases:
            pi = self.fake_pi([], 0, help_text=replaced(stub_help(), STUB_THINKING_LINE, line))
            code, out, err = self.tool_split(repo, "doctor", "--provider", "step", "--model", "step-5-preview",
                                             "--thinking", level, pi_cmd=pi)
            self.assertEqual(code, exit_code, out + err)
            facts = json.loads(out)
            self.assertEqual(facts["pi_help"]["thinking_levels"], levels, level)
            self.assertEqual((facts["problems"], facts["ok"]), (problems, not problems), level)


# ---------------------------------------------------------------------------
# 事件流：端到端（LB-EVENTS-009–021）
# ---------------------------------------------------------------------------

class EventStreamRunTests(EventsCase):
    """端到端：自定义事件流经 run → collect 后的落盘结果与退出码。"""

    def test_LB_EVENTS_013_response_model_differs_is_recorded_not_compared(self):
        """LB-EVENTS-013（:2323-2328、:2361-2362、:2376-2378）。
        验收：01-A07；C.4“实际模型与思考级别证据”缺口“responseModel 与要求不同”。

        responseModel 与要求的 model 不同，只记入 response_models，不参与 model_match：ok=true，run 退出 0。
        可疑点：网关替换了模型也不会被判为不符（legacy-inventory 4.15“模型字段来源”）。
        """
        repo = self.prepared_repo("resp-model")
        code, out, err = self.run_fake(repo, ok_events(response_model="step-5-preview-gateway-2026"))
        self.assertEqual(code, 0, out + err)
        ev = self.events_summary(repo)
        self.assertEqual(ev["actual_models"], [{"provider": "step", "model": "step-5-preview"}])
        self.assertEqual(ev["response_models"], ["step-5-preview-gateway-2026"])
        self.assertEqual((ev["model_match"], ev["ok"], ev["problems"]), (True, True, []))
        self.assertEqual(self.state(repo), "NEEDS_REVIEW")
        self.assertIn("- 实际模型：step/step-5-preview（一致：是）", self.summary_md(repo))

    def test_LB_EVENTS_013_missing_provider_and_model_fields(self):
        """LB-EVENTS-013（:2324、:2328、:2361-2362）、LB-EVENTS-021（:3401-3404、:3348-3349）。
        验收：01-A07；C.4“实际模型与思考级别证据”缺口“provider/model 字段缺失”。

        assistant 消息没有 provider/model 字段：actual_models 记为字符串 "None"，model_match=false，
        problem 中第一个 %s 是元组列表的 repr；有 assistant 消息所以状态仍是 NEEDS_REVIEW，run 退出 1。
        """
        repo = self.prepared_repo("no-model-fields")
        events = ok_events()
        for event in events:
            message = event.get("message")
            if isinstance(message, dict) and message.get("role") == "assistant":
                message.pop("provider", None)
                message.pop("model", None)
        code, out, err = self.run_fake(repo, events)
        self.assertEqual(code, 1, out + err)
        ev = self.events_summary(repo)
        problem = "实际模型 [('None', 'None')] 与要求 step/step-5-preview 不一致或缺失"
        self.assertEqual(ev["actual_models"], [{"provider": "None", "model": "None"}])
        self.assertEqual((ev["model_match"], ev["ok"], ev["problems"]), (False, False, [problem]))
        record = self.state_record(repo)
        self.assertEqual((record["state"], record["events_ok"]), ("NEEDS_REVIEW", False))
        md = self.summary_md(repo)
        self.assertIn("- 实际模型：None/None（一致：否）", md)
        self.assertIn("## 执行完整性问题", md)
        self.assertIn("- " + problem, md)

    def test_LB_EVENTS_017_duplicate_message_end_double_counts_usage(self):
        """LB-EVENTS-016/017（_add_usage 按增量累加、不去重，:2081-2093、:2218-2226）、LB-EVENTS-020（:2872、:4505-4515）。
        验收：01-A07；01-A06 的旧对照；兼容矩阵 D-17。

        锁定现状：最后一条 assistant message_end 重复投递时，用量与费用**重复累计**（input/output 2000/400 →
        3000/600，费用 0.00086 → 0.00129），assistant_messages 从 2 变 3，ok 仍为 true、run 退出 0。
        这是已登记风险 D-17（旧摘要中的用量和费用可能重复计数）；新记账归 07（01-D08），不继承旧摘要。
        """
        repo = self.prepared_repo("dup-message-end")
        events = ok_events()
        index = final_message_index(events)
        events.insert(index + 1, copy.deepcopy(events[index]))
        code, out, err = self.run_fake(repo, events)
        self.assertEqual(code, 0, out + err)
        ev = self.events_summary(repo)
        self.assertEqual((ev["ok"], ev["problems"], ev["complete"]), (True, [], True))
        self.assertEqual(ev["assistant_messages"], 3)
        self.assertEqual(ev["event_counts"]["message_end"], 4)
        self.assertEqual(ev["usage"], {"input": 3000, "output": 600, "cacheRead": 0, "cacheWrite": 0,
                                       "totalTokens": 3600})
        self.assertEqual((ev["cost"]["total"], ev["cost"]["status"], ev["cost"]["unpriced_messages"]),
                         (0.00129, "estimated", 0))
        self.assertEqual(self.state(repo), "NEEDS_REVIEW")
        self.assertIn("- 用量：input 3000 / output 600 / cacheRead 0 / cacheWrite 0 · 费用 0.00129（estimated）",
                      self.summary_md(repo))
        code, out = self.tool(repo, "status", "--json")
        self.assertEqual(code, 0, out)
        row = json.loads(out)[0]
        self.assertEqual((row["tokens"], row["cost"], row["cost_status"]), (3600, 0.00129, "estimated"))

    def test_LB_EVENTS_009_empty_stream_is_infra_failure(self):
        """LB-EVENTS-009/011（:2172、:2316-2318、:2339-2362）、LB-EVENTS-018/019（:2179-2180、:2334-2336）、
        LB-EVENTS-021（:3401-3402）。验收：01-A07；01-A11 的旧对照。

        假 pi 不输出任何事件、退出 0：摘要 4 条 problem（空流 → 结束事件 → stopReason=None → 实际模型 []），
        token 全为 0（不是 null）、费用 null/unknown；assistant_messages=0 → 状态 INFRA_FAILURE，run 退出 1。
        """
        repo = self.prepared_repo("empty-stream")
        code, out, err = self.run_fake(repo, [], files={})
        self.assertEqual(code, 1, out + err)
        ev = self.events_summary(repo)
        self.assertEqual(ev["problems"], [EMPTY_STREAM, NO_TERMINAL, "最终 assistant stopReason=None",
                                          "实际模型 [] 与要求 step/step-5-preview 不一致或缺失"])
        self.assertEqual((ev["lines"], ev["event_counts"], ev["parse_error_lines"], ev["truncated"]), (0, {}, [], False))
        self.assertEqual((ev["terminal_event"], ev["complete"], ev["session_header"]), (None, False, None))
        self.assertEqual((ev["final_stop_reason"], ev["final_error"], ev["assistant_messages"]), (None, None, 0))
        self.assertEqual((ev["actual_models"], ev["model_match"]), ([], False))
        self.assertEqual(ev["usage"], ZERO_USAGE)
        self.assertEqual((ev["cost"]["total"], ev["cost"]["status"], ev["cost"]["unpriced_messages"]),
                         (None, "unknown", 0))
        self.assertEqual(self.jload(self.rd(repo) / "report-status.json"), {"status": "missing"})
        self.assertEqual(self.jload(self.rd(repo) / "observations.json")["collect_errors"], [])
        record = self.state_record(repo)
        self.assertEqual((record["state"], record["exit_code"], record["events_ok"]), ("INFRA_FAILURE", 0, False))

    def test_LB_EVENTS_009_unterminated_valid_last_line_is_truncated(self):
        """LB-EVENTS-009（:2308、:2343-2344）、LB-EVENTS-011。验收：01-A07；01-A11 的旧对照。

        最后一行是合法 JSON（agent_settled）但没有行尾：能解析、complete=true，仍报“最后一行不完整”，
        ok=false；有 assistant 消息，状态 NEEDS_REVIEW，run 退出 1。
        """
        repo = self.prepared_repo("unterminated")
        events: List[EventLine] = list(ok_events(settled=False))
        events.append(b'{"type": "agent_settled"}')
        code, out, err = self.run_fake(repo, events)
        self.assertEqual(code, 1, out + err)
        ev = self.events_summary(repo)
        self.assertEqual((ev["truncated"], ev["parse_error_lines"], ev["lines"]), (True, [], 19))
        self.assertEqual((ev["terminal_event"], ev["complete"]), ("agent_settled", True))
        self.assertEqual((ev["ok"], ev["problems"]), (False, [TRUNCATED]))
        record = self.state_record(repo)
        self.assertEqual((record["state"], record["events_ok"]), ("NEEDS_REVIEW", False))

    def test_LB_EVENTS_021_nonzero_pi_exit_with_complete_events(self):
        """LB-EVENTS-021（:3348-3349、:3395-3404、:4173-4174）。验收：01-A07（G1）；01-A05 的旧对照。

        锁定现状：事件完整、ok=true 而 Pi 退出码为 5 时，collect 与 run 都不看退出码：状态 NEEDS_REVIEW、
        run 退出 0；只有 verdict 的 G1 记“Pi 退出码为 5”，check 通过后 PASS 仍被拒（退出 1），状态不变。
        可疑点：run 退出 0 不代表 Pi 正常结束（legacy-inventory 4.15“退出码”，此前只是源码推断）。
        """
        repo = self.prepared_repo("pi-exit-5")
        code, out, err = self.run_fake(repo, ok_events(), exit_code=5)
        self.assertEqual(code, 0, out + err)
        ev = self.events_summary(repo)
        self.assertEqual((ev["complete"], ev["ok"], ev["problems"]), (True, True, []))
        record = self.state_record(repo)
        self.assertEqual((record["state"], record["exit_code"], record["events_ok"]), ("NEEDS_REVIEW", 5, True))
        self.assertEqual(self.jload(self.rd(repo) / "run.json")["exit_code"], 5)
        self.assertIn("- Pi 退出码：5 ·", self.summary_md(repo))
        code, out = self.tool(repo, "check", self.attempt_ref(1))
        self.assertEqual(code, 0, out)
        code, out, err = self.tool_split(repo, "verdict", self.attempt_ref(1), "--verdict", "PASS",
                                         "--review", self.review(repo, "PASS"))
        self.assertEqual(code, self.pd.EXIT_FAIL, out + err)
        self.assertEqual([line for line in out.splitlines() if line.startswith("GATE ")], ["GATE G1 Pi 退出码为 5"])
        self.assertIn("ERROR: PASS 被拒绝：门禁 G1 未通过。", err)
        self.assertEqual(self.state(repo), "NEEDS_REVIEW")

    def test_LB_EVENTS_018_missing_usage_tokens_are_zero_and_cost_unknown(self):
        """LB-EVENTS-018（token 缺失输出 0，:2179-2180、:2390、:2872、:4505）、LB-EVENTS-019（:2334-2336、:2391-2392）、
        LB-EVENTS-020（status 的 COST 列，:4494-4515）。验收：01-A07；01-A06 的旧对照；兼容矩阵 D-18、D-19。

        锁定现状：assistant 消息的 usage 是空对象时，token 各项输出 **0 而不是 null**，没有用量完整性字段；
        费用 total=null、status=unknown、unpriced_messages=0，且不产生 problem（ok=true，run 退出 0）。
        summary.md 用量行印 0、费用写“未知”；status --json 的 tokens 为 0（不是 null），COST 列为 unknown。
        可疑点：与设计文档 4.3.7“null 表示未知”冲突，旧的 0 不能当作“已知为 0”（D-18）；未知费用不算问题（D-19）。
        """
        repo = self.prepared_repo("no-usage")
        code, out, err = self.run_fake(repo, ok_events(usage={}))
        self.assertEqual(code, 0, out + err)
        ev = self.events_summary(repo)
        self.assertEqual((ev["ok"], ev["problems"]), (True, []))
        self.assertEqual(ev["usage"], ZERO_USAGE)
        self.assertEqual(ev["cost"], {"total": None, "status": "unknown", "unpriced_messages": 0,
                                      "note": "Pi 按模型目录价格估算；以提供商或网关账单为准"})
        self.assertIn("- 用量：input 0 / output 0 / cacheRead 0 / cacheWrite 0 · 费用 未知（unknown）",
                      self.summary_md(repo))
        code, out = self.tool(repo, "status", "--json")
        self.assertEqual(code, 0, out)
        row = json.loads(out)[0]
        self.assertEqual((row["tokens"], row["cost"], row["cost_status"]), (0, None, "unknown"))
        code, out = self.tool(repo, "status")
        self.assertEqual(code, 0, out)
        rows = [line.split() for line in out.splitlines() if "attempt-001" in line]
        self.assertEqual(len(rows), 1, out)
        self.assertEqual((rows[0][1], rows[0][-1]), ("NEEDS_REVIEW", "unknown"))

    def test_LB_EVENTS_015_stderr_warning_flags(self):
        """LB-EVENTS-015（STDERR_WARNING_PATTERNS :261-266；:2329-2332、:2363-2365；summary.md :2954-2955、:2972）。
        验收：01-A07；C.4“实际模型与思考级别证据”缺口“stderr 警告（:261-266、2363-2365）”。

        stderr.log 去 ANSI 后依次匹配四种标记：custom_model_id、invalid_thinking、unknown_option 三类各产生一条
        problem（run 退出 1，状态 NEEDS_REVIEW）；extension_error 只进 stderr_flags。summary.md 的“复审需要关注”
        对全部四个标记都写“stderr 标记：…”。
        """
        repo = self.prepared_repo("stderr-flags")
        stderr_text = ("Warning: Using custom model id \"step-5-preview\"\n"
                       "Warning: Invalid \x1b[1mthinking\x1b[0m level \"ultra\"\n"
                       "Error: Unknown option --bogus\n"
                       "Extension error: demo failed to load\n")
        code, out, err = self.run_fake(repo, ok_events(), stderr_text=stderr_text)
        self.assertEqual(code, 1, out + err)
        ev = self.events_summary(repo)
        flags = ["custom_model_id", "invalid_thinking", "unknown_option", "extension_error"]
        self.assertEqual(ev["stderr_flags"], flags)
        self.assertEqual(ev["problems"], ["stderr 出现 custom_model_id 警告", "stderr 出现 invalid_thinking 警告",
                                          "stderr 出现 unknown_option 警告"])
        self.assertEqual((ev["complete"], ev["model_match"], ev["ok"]), (True, True, False))
        self.assertEqual(self.state(repo), "NEEDS_REVIEW")
        md = self.summary_md(repo)
        self.assertIn("## 复审需要关注", md)
        for flag in flags:
            self.assertIn("- stderr 标记：%s" % flag, md)


# ---------------------------------------------------------------------------
# 事件流：进程内（白盒，pd.summarize_events）
# ---------------------------------------------------------------------------

class SummarizeEventsWhiteBoxTests(EventsCase):
    """白盒：直接调用 pd.summarize_events 处理本文件构造的事件文件（不经 run/collect）。"""

    def test_LB_EVENTS_009_unparseable_lines_are_counted_not_fatal(self):
        """LB-EVENTS-009（:2201-2213、:2341-2342、:2367-2369）。白盒。验收：01-A07；01-A11 的旧对照；兼容矩阵 D-16。

        CRLF 行尾正常解析；空白行跳过但占行号、不计入 lines；普通文本、以 BOM 开头的对象、JSON 数组、
        JSON 字符串、非 UTF-8 字节都记入 parse_error_lines 并继续。complete 仍为 true，只有一条
        “事件流有 5 行无法解析”，ok=false。可疑点：旧实现没有独立的完整性维度，complete 与解析失败无关（D-16）。
        """
        base = ok_events()
        lines: List[EventLine] = [base[0], "this is not json", "   ",
                                  "﻿" + json.dumps({"type": "agent_start"}), "[1, 2]", '"just a string"',
                                  b"\xff\xfe{}\r\n"] + list(base[1:])
        ev, final_text = self.summarize(lines, eol="\r\n")
        self.assertEqual(ev["parse_error_lines"], [2, 4, 5, 6, 7])
        self.assertEqual(ev["lines"], 24)
        self.assertEqual(ev["problems"], ["事件流有 5 行无法解析"])
        self.assertEqual((ev["complete"], ev["truncated"], ev["ok"]), (True, False, False))
        self.assertEqual(ev["event_counts"]["agent_start"], 1)
        self.assertEqual(ev["assistant_messages"], 2)
        self.assertIn("## 执行报告", final_text)

    def test_LB_EVENTS_009_truncated_tail_depends_on_expects_settled(self):
        """LB-EVENTS-009、LB-EVENTS-011（:2294-2318、:2343-2349）。白盒。验收：01-A07；01-A11 的旧对照；兼容矩阵 D-15。

        stub ok 流（19 行）的最后一行 agent_settled 只留前一半字节、无行尾：第 19 行无法解析且 truncated=true。
        expects_settled 为 True 或 None 时 complete=false 并报“没有 agent_settled…”；为 False 时按 agent_end
        判为 complete=true，但 ok 仍为 false（解析失败与截断两条 problem）。
        """
        events: List[EventLine] = list(ok_events(settled=False))
        cut = json.dumps({"type": "agent_settled"}).encode("ascii")
        events.append(cut[:len(cut) // 2])
        for expects in (True, None):
            ev, _ = self.summarize(events, expects_settled=expects)
            self.assertEqual((ev["lines"], ev["parse_error_lines"], ev["truncated"]), (19, [19], True), expects)
            self.assertEqual((ev["terminal_event"], ev["complete"]), ("agent_end", False), expects)
            self.assertEqual(ev["problems"], ["事件流有 1 行无法解析", TRUNCATED, NO_SETTLED], expects)
        ev, _ = self.summarize(events, expects_settled=False)
        self.assertEqual((ev["terminal_event"], ev["complete"], ev["ok"]), ("agent_end", True, False))
        self.assertEqual(ev["problems"], ["事件流有 1 行无法解析", TRUNCATED])

    def test_LB_EVENTS_011_agent_end_fallback_by_expects_settled(self):
        """LB-EVENTS-011（:2294-2298、:2312-2315、:2346-2349）。白盒。验收：01-A07；01-A11 的旧对照。

        没有 agent_settled、以 agent_end(willRetry=false) 结束的流：expects_settled=True/None → 不完整并报
        “没有 agent_settled…”；False → 完整。False 且最后一个 agent_end 的 willRetry=true → 不完整，报通用文本。
        False 时 agent_end(willRetry=true) → agent_start → … → agent_end(false) 判为完整。
        最后一个 agent_end 缺少 willRetry 字段或为 null 时按假处理（bool(None)，:2296）：expects_settled=False 时完整。
        """
        nosettle = ok_events(settled=False)
        for expects in (True, None):
            ev, _ = self.summarize(nosettle, expects_settled=expects)
            self.assertEqual((ev["terminal_event"], ev["complete"], ev["problems"]),
                             ("agent_end", False, [NO_SETTLED]), expects)
        ev, _ = self.summarize(nosettle, expects_settled=False)
        self.assertEqual((ev["terminal_event"], ev["complete"], ev["ok"]), ("agent_end", True, True))
        for last_end in ({"type": "agent_end", "messages": []}, {"type": "agent_end", "messages": [], "willRetry": None}):
            ev, _ = self.summarize(nosettle[:-1] + [last_end], expects_settled=False)
            self.assertEqual((ev["terminal_event"], ev["complete"], ev["ok"], ev["problems"]),
                             ("agent_end", True, True, []), last_end)
        retry_last = nosettle[:-1] + [{"type": "agent_end", "messages": [], "willRetry": True}]
        ev, _ = self.summarize(retry_last, expects_settled=False)
        self.assertEqual((ev["complete"], ev["problems"]), (False, [NO_TERMINAL]))
        retried = (nosettle[:-1] + [{"type": "agent_end", "messages": [], "willRetry": True},
                                    {"type": "agent_start"}, {"type": "turn_start"}] + [nosettle[-1]])
        ev, _ = self.summarize(retried, expects_settled=False)
        self.assertEqual((ev["event_counts"]["agent_end"], ev["complete"], ev["problems"]), (2, True, []))

    def test_LB_EVENTS_011_events_after_agent_settled(self):
        """LB-EVENTS-011（:2214-2215、:2299-2311）、LB-EVENTS-012（:2319）；legacy-inventory 9.8 核对补充。白盒。
        验收：01-A07；01-A11 的旧对照。

        agent_settled 之后：
        - 一条没有 message_start 的 assistant message_end（非 WORK 事件）：complete 仍为 true，它成为新的最终消息，
          用量照常累加（input 3000），ok=true —— 可疑：终止后的内容静默替换最终消息（legacy-inventory 4.15）；
        - 再来任一 WORK 事件（WORK_EVENTS 的四种：agent_start、turn_start、message_start、tool_execution_start，逐个验证）：
          complete=false，报通用的“没有观察到完整的结束事件”；
        - 再来 turn_start 后又来 agent_end(willRetry=false)：仍不完整（有过 agent_settled 后，agent_end 不再清除
          待完成的工作，:2297 的 settled_count == 0）；
        - 再来 turn_start 后又来 agent_settled：恢复完整（agent_settled 总是清除待完成的工作，:2299-2301）；
        - 再来 agent_end(willRetry=true)：不改变结果，仍完整。
        """
        settled = ok_events()
        ev, final_text = self.summarize(settled + [assistant("LATE REPLY")])
        self.assertEqual((ev["terminal_event"], ev["complete"], ev["ok"], ev["problems"]),
                         ("agent_settled", True, True, []))
        self.assertEqual((ev["assistant_messages"], final_text), (3, "LATE REPLY"))
        self.assertEqual((ev["usage"]["input"], ev["usage"]["totalTokens"]), (3000, 3600))
        work_events = [{"type": "agent_start"}, {"type": "turn_start"},
                       {"type": "message_start", "message": {"role": "assistant", "content": []}},
                       {"type": "tool_execution_start", "toolCallId": "c9", "toolName": "read",
                        "args": {"path": "src/normalize.py"}}]
        for work in work_events:
            ev, _ = self.summarize(settled + [work])
            self.assertEqual((ev["terminal_event"], ev["complete"], ev["ok"], ev["problems"]),
                             ("agent_settled", False, False, [NO_TERMINAL]), work["type"])
        self.assertEqual([work["type"] for work in work_events], list(self.pd.WORK_EVENTS))
        ev, _ = self.summarize(settled + [{"type": "turn_start"},
                                          {"type": "agent_end", "messages": [], "willRetry": False}])
        self.assertEqual((ev["terminal_event"], ev["complete"], ev["problems"]), ("agent_settled", False, [NO_TERMINAL]))
        self.assertEqual((ev["event_counts"]["agent_end"], ev["event_counts"]["agent_settled"]), (2, 1))
        ev, _ = self.summarize(settled + [{"type": "turn_start"}, {"type": "agent_settled"}])
        self.assertEqual((ev["terminal_event"], ev["complete"], ev["ok"], ev["problems"]),
                         ("agent_settled", True, True, []))
        ev, _ = self.summarize(settled + [{"type": "agent_end", "messages": [], "willRetry": True}])
        self.assertEqual((ev["terminal_event"], ev["complete"], ev["ok"]), ("agent_settled", True, True))

    def test_LB_EVENTS_014_partial_thinking_level_reporting(self):
        """LB-EVENTS-014（:2326-2327、:2337、:2350-2352、:2379-2382）。白盒。
        验收：01-A07；C.4“实际模型与思考级别证据”缺口“回报级别与要求一致的正例”“部分消息回报”。

        - 只有最终消息回报 providerThinkingLevel=high（第一条不回报）：provider_reported，不告警，ok=true；
        - 两条分别回报 low 与 high：problem 只列不一致的级别 ['low']；
        - 都不回报：thinking_evidence 以“not_reported：”开头，不算 problem。
        """
        events = ok_events(provider="step", model="step-5-preview")
        index = final_message_index(events)
        final = copy.deepcopy(events[index])
        final["message"]["providerThinkingLevel"] = "high"
        partial = events[:index] + [final] + events[index + 1:]
        ev, _ = self.summarize(partial)
        self.assertEqual((ev["provider_thinking_levels"], ev["thinking_evidence"], ev["problems"], ev["ok"]),
                         (["high"], "provider_reported", [], True))
        mixed = ok_events(message_extra={"providerThinkingLevel": "low"})
        mixed[final_message_index(mixed)]["message"]["providerThinkingLevel"] = "high"
        first_end = next(e for e in mixed if e.get("type") == "message_end" and e["message"].get("role") == "assistant")
        self.assertEqual(first_end["message"]["providerThinkingLevel"], "low")  # 第一条 assistant 仍回报 low
        ev, _ = self.summarize(mixed)
        self.assertEqual(ev["provider_thinking_levels"], ["high", "low"])
        self.assertEqual(ev["problems"], ["提供商报告的思考级别 ['low'] 与要求的 high 不一致"])
        ev, _ = self.summarize(ok_events())
        self.assertEqual((ev["provider_thinking_levels"], ev["problems"]), ([], []))
        self.assertTrue(ev["thinking_evidence"].startswith("not_reported："), ev["thinking_evidence"])

    def test_LB_EVENTS_013_every_assistant_pair_must_match(self):
        """LB-EVENTS-013（:2323-2328、:2361-2362）。白盒。验收：01-A07；C.4“实际模型与思考级别证据”。

        - 只缺 model：actual_models 为 step/None；
        - 一条匹配、一条是别的模型：actual_models 去重排序后两项，model_match=false（要求每一对都一致）。
        """
        events = ok_events()
        events[final_message_index(events)]["message"].pop("model")
        ev, _ = self.summarize(events)
        self.assertEqual(ev["actual_models"], [{"provider": "step", "model": "None"},
                                               {"provider": "step", "model": "step-5-preview"}])
        self.assertIs(ev["model_match"], False)
        self.assertEqual(ev["problems"], ["实际模型 [('step', 'None'), ('step', 'step-5-preview')] "
                                          "与要求 step/step-5-preview 不一致或缺失"])
        events = ok_events()
        events[final_message_index(events)]["message"]["model"] = "step-3.5-flash"
        ev, _ = self.summarize(events)
        self.assertEqual((ev["model_match"], len(ev["actual_models"])), (False, 2))
        self.assertEqual(ev["problems"], ["实际模型 [('step', 'step-3.5-flash'), ('step', 'step-5-preview')] "
                                          "与要求 step/step-5-preview 不一致或缺失"])

    def test_LB_EVENTS_017_usage_sources_and_non_sources(self):
        """LB-EVENTS-016/017（_add_usage :2081-2093；来源 :2226、:2228、:2234、:2238；不累加 :2201-2306）。白盒。
        验收：01-A07；01-A06 的旧对照。

        累加：assistant 与 toolResult 的 message_end.usage、entry_appended{type=usage}、compaction_end.result.usage；
        不累加：message_update 顶层 usage、turn_end.message.usage、agent_end.messages[].usage。
        bool 也按数值累加（cacheRead=True 计为 1）；无正数费用而 totalTokens>0 的 usage 计入 unpriced_messages
        （按 usage 对象计，含压缩：本例的压缩 usage 没有费用，unpriced_messages=1）。本例的 partial 同时来自
        priced_missing=1 与 compaction，分不出是哪一条造成的；“compaction 单独使费用为 partial”由
        test_LB_EVENTS_019_compaction_cost_status 锁定。可疑点：各来源是否重叠未核实，旧实现全部相加。
        """
        def usage(tokens: int, cost: Optional[float], **extra: Any) -> Dict[str, Any]:
            data: Dict[str, Any] = {"input": tokens, "output": 0, "cacheRead": 0, "cacheWrite": 0,
                                    "totalTokens": tokens}
            if cost is not None:
                data["cost"] = {"total": cost}
            data.update(extra)
            return data

        ignored = usage(100000, 1.0)
        lines: List[EventLine] = [
            {"type": "session", "version": 3, "id": "s", "timestamp": "t", "cwd": "{{cwd}}"},
            {"type": "agent_start"},
            {"type": "message_update", "usage": ignored},
            {"type": "message_end", "message": {"role": "toolResult", "usage": usage(10, 0.0001)}},
            {"type": "entry_appended", "entry": {"type": "usage", "usage": usage(1, 0.00001)}},
            {"type": "entry_appended", "entry": {"type": "note", "usage": ignored}},
            {"type": "compaction_end", "result": {"usage": usage(1000, None)}},
            assistant("done", usage=usage(100, 0.001, cacheRead=True)),
            {"type": "turn_end", "message": {"role": "assistant", "usage": ignored}},
            {"type": "agent_end", "messages": [{"role": "assistant", "usage": ignored}], "willRetry": False},
            {"type": "agent_settled"},
        ]
        ev, _ = self.summarize(lines)
        self.assertEqual(ev["usage"], {"input": 1111, "output": 0, "cacheRead": 1, "cacheWrite": 0, "totalTokens": 1111})
        self.assertEqual((ev["compactions"], ev["assistant_messages"]), (1, 1))
        self.assertEqual((ev["cost"]["total"], ev["cost"]["status"], ev["cost"]["unpriced_messages"]),
                         (0.00111, "partial", 1))
        self.assertEqual((ev["ok"], ev["problems"]), (True, []))

    def test_LB_EVENTS_019_cost_status_rules(self):
        """LB-EVENTS-019（:2089-2093、:2334-2336、:2390-2392）、LB-EVENTS-018。白盒。验收：01-A07；01-A06 的旧对照；D-18、D-19。

        - 两条都有正数费用：estimated，total 为和；
        - 一条有费用、一条 cost.total=0 而 totalTokens>0：partial，total 只是已知部分，unpriced_messages=1；
        - 费用为 0 或负数：按“未定价”计；全部未定价时 total=null、status=unknown（stub 的 STUB_NOCOST 同类，D-19）；
        - 只有 input、没有 totalTokens 的无价 usage 不计入 unpriced_messages；
        - 没有 assistant、只有 toolResult 的有价用量：token 照常累加，费用仍为 null/unknown；
        - 只有 session 一行（stub startfail 形态，D-18）：token 全为 0，费用 null/unknown。
        所有情形都不因费用状态产生 problem。
        """
        def cost_of(ev: Dict[str, Any]) -> Tuple[Any, Any, Any]:
            return ev["cost"]["total"], ev["cost"]["status"], ev["cost"]["unpriced_messages"]

        def stream(*messages: Dict[str, Any]) -> List[EventLine]:
            return [{"type": "agent_start"}] + list(messages) + [{"type": "agent_settled"}]

        priced = {"input": 10, "totalTokens": 10, "cost": {"total": 0.002}}
        zero = {"input": 10, "totalTokens": 10, "cost": {"total": 0}}
        negative = {"input": 10, "totalTokens": 10, "cost": {"total": -0.5}}
        input_only = {"input": 10}
        ev, _ = self.summarize(stream(assistant("a", "toolUse", priced), assistant("b", usage=priced)))
        self.assertEqual(cost_of(ev), (0.004, "estimated", 0))
        self.assertEqual(ev["problems"], [])
        ev, _ = self.summarize(stream(assistant("a", "toolUse", priced), assistant("b", usage=zero)))
        self.assertEqual(cost_of(ev), (0.002, "partial", 1))
        self.assertEqual(ev["problems"], [])
        ev, _ = self.summarize(stream(assistant("a", "toolUse", zero), assistant("b", usage=negative)))
        self.assertEqual(cost_of(ev), (None, "unknown", 2))
        self.assertEqual((ev["usage"]["totalTokens"], ev["problems"]), (20, []))
        ev, _ = self.summarize(stream(assistant("a", usage=input_only)))
        self.assertEqual(cost_of(ev), (None, "unknown", 0))
        self.assertEqual((ev["usage"]["input"], ev["usage"]["totalTokens"], ev["ok"]), (10, 0, True))
        ev, _ = self.summarize(stream({"type": "message_end", "message": {"role": "toolResult", "usage": priced}}))
        self.assertEqual(cost_of(ev), (None, "unknown", 0))
        self.assertEqual(ev["usage"]["input"], 10)
        self.assertEqual(ev["problems"], ["最终 assistant stopReason=None",
                                          "实际模型 [] 与要求 step/step-5-preview 不一致或缺失"])
        ev, _ = self.summarize([{"type": "session", "version": 3, "id": "stub", "timestamp": "t", "cwd": "{{cwd}}"}])
        self.assertEqual(ev["usage"], ZERO_USAGE)
        self.assertEqual(cost_of(ev), (None, "unknown", 0))
        self.assertEqual(ev["problems"], [NO_TERMINAL, "最终 assistant stopReason=None",
                                          "实际模型 [] 与要求 step/step-5-preview 不一致或缺失"])

    def test_LB_EVENTS_019_compaction_cost_status(self):
        """LB-EVENTS-017/019（:2235-2238、:2334-2336、:2390-2392；legacy-inventory 4.7 费用表“出现过 compaction_end”两行）。
        白盒。验收：01-A07；01-A06 的旧对照；11.5 第 6 条“compaction_end 的用量”“partial 费用”。

        这里带 totalTokens 的 usage 都有正数费用（priced_missing=0），所以 partial 只能来自 compaction：
        - 同样的流没有 compaction：estimated；
        - compaction_end.result.usage 有正数费用：partial，total 为全部之和（含压缩费用），unpriced_messages=0，
          压缩用量计入 usage；
        - compaction_end 没有 result、result 没有 usage、或 usage 只有 input 没有 totalTokens：仍为 partial，
          unpriced_messages=0（compactions 按事件计数，与有无 usage 无关）；
        - 有 compaction、但所有费用都为 0（cost_total=0）：total=null、status=unknown（**不是** partial），
          unpriced_messages 含压缩 usage（2）；
        - 有 compaction、压缩费用为正，但没有 assistant 消息：unknown（先看有没有 assistant）。
        费用状态都不产生 problem。
        """
        def cost_of(ev: Dict[str, Any]) -> Tuple[Any, Any, Any]:
            return ev["cost"]["total"], ev["cost"]["status"], ev["cost"]["unpriced_messages"]

        def stream(*events: Dict[str, Any]) -> List[EventLine]:
            return [{"type": "agent_start"}] + list(events) + [{"type": "agent_settled"}]

        priced = {"input": 10, "totalTokens": 10, "cost": {"total": 0.002}}
        compacted = {"input": 500, "totalTokens": 500, "cost": {"total": 0.01}}
        final = assistant("done", usage=priced)
        ev, _ = self.summarize(stream(final))
        self.assertEqual((cost_of(ev), ev["compactions"], ev["problems"]), ((0.002, "estimated", 0), 0, []))
        ev, _ = self.summarize(stream({"type": "compaction_start"},
                                      {"type": "compaction_end", "result": {"usage": compacted}}, final))
        self.assertEqual((cost_of(ev), ev["compactions"], ev["problems"]), ((0.012, "partial", 0), 1, []))
        self.assertEqual((ev["usage"]["input"], ev["usage"]["totalTokens"]), (510, 510))
        for compaction in ({"type": "compaction_end"}, {"type": "compaction_end", "result": {}},
                           {"type": "compaction_end", "result": {"usage": {"input": 500}}}):
            ev, _ = self.summarize(stream(compaction, final))
            self.assertEqual((cost_of(ev), ev["compactions"], ev["problems"]), ((0.002, "partial", 0), 1, []),
                             compaction)
        zero = {"input": 10, "totalTokens": 10, "cost": {"total": 0}}
        ev, _ = self.summarize(stream({"type": "compaction_end", "result": {"usage": {"input": 500, "totalTokens": 500}}},
                                      assistant("done", usage=zero)))
        self.assertEqual((cost_of(ev), ev["compactions"], ev["problems"]), ((None, "unknown", 2), 1, []))
        self.assertEqual(ev["usage"]["totalTokens"], 510)
        ev, _ = self.summarize(stream({"type": "compaction_end", "result": {"usage": compacted}}))
        self.assertEqual((cost_of(ev), ev["compactions"], ev["assistant_messages"]), ((None, "unknown", 0), 1, 0))

    def test_LB_EVENTS_026_non_numeric_total_tokens_raises(self):
        """LB-EVENTS-026（:2092）。白盒。验收：01-A07；01-A06 的旧对照。

        锁定现状：usage.totalTokens 为非空字符串且没有正数费用时，summarize_events 抛出未捕获的 TypeError；
        空字符串经 `or 0` 不报错。端到端后果（run 停在 COLLECTING、wait 持续返回 3）不在本文件验证。
        """
        with self.assertRaises(TypeError) as ctx:
            self.summarize([assistant(usage={"input": 1, "totalTokens": "12"}), {"type": "agent_settled"}])
        self.assertIn("'>' not supported between instances of 'str' and 'int'", str(ctx.exception))
        ev, _ = self.summarize([assistant(usage={"input": 1, "totalTokens": ""}), {"type": "agent_settled"}])
        self.assertEqual((ev["usage"]["input"], ev["usage"]["totalTokens"], ev["cost"]["unpriced_messages"]), (1, 0, 0))

    def test_LB_EVENTS_015_stderr_flags_need_existing_file(self):
        """LB-EVENTS-015（:2329-2332、:2363-2365）。白盒。验收：01-A07；C.4“实际模型与思考级别证据”（stderr 警告）。

        - 不传 stderr_path（None）：即使 events.jsonl 同目录就有含警告的 stderr.log，也不读取、不检查
          （summarize_events 不自己找文件，只看调用方传入的路径）；
        - stderr_path 指向不存在的文件：不抛异常，stderr_flags 为空；
        - 只有 Extension error：stderr_flags=["extension_error"]，不产生 problem，ok=true；
        - 非 UTF-8 字节按 errors=replace 读取，不抛异常。
        """
        events = ok_events()
        warning = "Error: Unknown option --bogus\n"
        ev, _ = self.summarize(events, stderr_text=warning, stderr_arg="none")
        self.assertEqual((self.inproc_dir / "stderr.log").read_text(encoding="utf-8"), warning)
        self.assertTrue((self.inproc_dir / "events.jsonl").is_file())  # 与 stderr.log 同目录（同 run 目录的布局）
        self.assertEqual((ev["stderr_flags"], ev["problems"], ev["ok"]), ([], [], True))
        ev, _ = self.summarize(events, stderr_arg="missing")
        self.assertEqual((ev["stderr_flags"], ev["problems"], ev["ok"]), ([], [], True))
        ev, _ = self.summarize(events, stderr_text=warning)  # 对照：同样的文件，传入路径时会检出
        self.assertEqual((ev["stderr_flags"], ev["problems"]), (["unknown_option"], ["stderr 出现 unknown_option 警告"]))
        ev, _ = self.summarize(events, stderr_text="Extension error: boom\n")
        self.assertEqual((ev["stderr_flags"], ev["problems"], ev["ok"]), (["extension_error"], [], True))
        ev, _ = self.summarize(events, stderr_text=b"\xff\xfe\x80 not utf-8\nUnknown option --x\n")
        self.assertEqual((ev["stderr_flags"], ev["problems"]), (["unknown_option"], ["stderr 出现 unknown_option 警告"]))


class SourceFactsTests(unittest.TestCase):

    def test_legacy_source_is_locked_revision(self):
        """新增：被测字节核对（legacy_harness.legacy_facts）。验收：01-A07（回归映射须指明被测提交）。

        默认 KIT 下，scripts/pi_dispatch.py 把 CRLF 归一为 LF 之后的 sha256 必须等于 a4fa199 的锁定摘要（blob 字节）。
        按归一后的摘要比较，是因为该文件没有 eol 属性、本机系统级 core.autocrlf=true：重新检出、新克隆或新建
        worktree 得到 CRLF 字节，内容仍是 a4fa199。原始字节的摘要照样记录（pi_dispatch_sha256），失败信息同时给出两者。
        设置 CODEKIT_LEGACY_KIT_DIR 做变异反测时本用例会失败，这是预期（说明测的不是 a4fa199 的内容）。
        """
        facts = legacy_facts()
        detail = "raw=%s lf=%s locked=%s" % (facts["pi_dispatch_sha256"], facts["pi_dispatch_sha256_lf"],
                                             facts["locked_pi_dispatch_sha256"])
        self.assertTrue(facts["pi_dispatch_matches_a4fa199"], detail)
        self.assertEqual(facts["pi_dispatch_sha256_lf"], facts["locked_pi_dispatch_sha256"], detail)


if __name__ == "__main__":
    unittest.main(verbosity=2)
