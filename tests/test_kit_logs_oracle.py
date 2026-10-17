"""scripts/kit_logs.py 的规划端 oracle（kit-logs v1，只读的 logs 子命令）。

依据：.agent/plans/kit-logs.v1.md 的 Behavior contract B0–B10；设计 §9 的 L 组（L1–L13）。
全部夹具都是合成的：会话记录（JSONL）与 .agent/runs 下的证据文件都在临时目录里现场生成，
不读取任何真实的会话记录或用户目录。文件名与键名在这里写成字面量，不从被测模块导入。
链接用例：Windows 上用 `cmd /c mklink /J` 建 junction，其它平台用指向目录的符号链接；建不了就 skipTest。
"""
from __future__ import annotations

import contextlib
import io
import itertools
import json
import os
import random
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import pi_dispatch as pd  # noqa: E402
import kit_logs  # noqa: E402


# ---------------------------------------------------------------------------
# 夹具与小工具
# ---------------------------------------------------------------------------

SINCE = "2026-10-17T10:00:00Z"
UNTIL = "2026-10-17T10:30:00Z"
IN_WINDOW = "2026-10-17T10:15:00Z"
STATE_AT = "2026-10-17T10:00:00Z"
MODEL_OBJ = {"provider": "bb", "model": "step-5-preview", "thinking": "high"}
USAGE_KEYS = ("input", "output", "cacheRead", "cacheWrite", "totalTokens")
TOKEN_KEYS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")
MATCH_RE = re.compile(r"^(?P<path>[^:\n]+):(?P<line>\d+): (?P<content>.*)$")
MAX_SUMMARY_BYTES = 65536


class Raw(str):
    """原样写入的一行（用于坏 JSON 等非法行）。"""


def put(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        data = data.encode("utf-8")
    path.write_bytes(data)


def dump(obj):
    return json.dumps(obj, ensure_ascii=False, indent=2) + "\n"


def transcript(path, rows):
    lines = []
    for row in rows:
        lines.append(row if isinstance(row, Raw) else json.dumps(row, ensure_ascii=False))
    put(path, "\n".join(lines) + "\n")


def usage(i=10, c=2, r=3, o=4):
    return {"input_tokens": i, "cache_creation_input_tokens": c, "cache_read_input_tokens": r, "output_tokens": o}


_OMIT = object()  # rec(stop=_OMIT)：不写 stop_reason 键（缺失）


def rec(rid, *, ts=IN_WINDOW, model="model-a", sidechain=False, use=None, has_model=True, has_side=True,
        stop="end_turn"):
    """stop 缺省为 end_turn（最终记录）；stop=None 为中间记录（null）；stop=_OMIT 为缺失。"""
    row = {
        "type": "assistant",
        "requestId": "req-" + rid,
        "sessionId": "session-synthetic",
        "message": {"id": rid, "role": "assistant",
                    "content": [{"type": "text", "text": "SYNTHETIC-CONTENT sk-ant-api03-SYNTHETIC-KEY-0123456789"}],
                    "usage": use if use is not None else usage()},
    }
    if ts is not None:
        row["timestamp"] = ts
    if has_model:
        row["message"]["model"] = model
    if has_side:
        row["isSidechain"] = sidechain
    if stop is not _OMIT:
        row["message"]["stop_reason"] = stop
    return row


def interim(rid, **kwargs):
    """子代理流式写法的中间记录：stop_reason 为 null，output_tokens 可能还未到终值。"""
    kwargs.setdefault("use", usage(o=8))
    return rec(rid, stop=None, **kwargs)


def es_summary(use=None, requested=MODEL_OBJ, complete=True, truncated=False, parse_error_lines=()):
    obj = {
        "lines": 3,
        "event_counts": {},
        "parse_error_lines": list(parse_error_lines),
        "truncated": truncated,
        "complete": complete,
        "requested_model": requested,
        "cost": {"total": None},
    }
    if use is not None:
        obj["usage"] = use
    return obj


def five(i, o, r, c, t):
    return {"input": i, "output": o, "cacheRead": r, "cacheWrite": c, "totalTokens": t}


def run_logs(argv, repo):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = kit_logs.main(list(argv), repo=str(repo))
        except SystemExit as exc:  # argparse
            code = exc.code if isinstance(exc.code, int) else 1
    return code, out.getvalue(), err.getvalue()


def match_lines(text):
    found = []
    for line in text.splitlines():
        m = MATCH_RE.match(line)
        if m:
            found.append((m.group("path"), int(m.group("line")), m.group("content")))
    return found


def snapshot(tree):
    """逐字节快照：相对路径 -> ('d',) 或 ('f', 字节)。不跟随任何链接（夹具里没有链接）。"""
    result = {}
    base = Path(tree)
    if not base.exists():
        return result
    for dirpath, dirnames, filenames in os.walk(str(base)):
        for name in dirnames:
            full = Path(dirpath) / name
            result[full.relative_to(base).as_posix()] = ("d",)
        for name in filenames:
            full = Path(dirpath) / name
            result[full.relative_to(base).as_posix()] = ("f", full.read_bytes())
    return result


class OracleBase(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="kit-logs-oracle-")).resolve()
        self.addCleanup(self._cleanup)
        self.links = []
        self.repo = self.root / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=str(self.repo), check=True)
        (self.repo / ".agent").mkdir()
        self.runs = self.repo / ".agent" / "runs"
        self.outside = self.root / "outside"
        self.outside.mkdir()

    def _cleanup(self):
        # 先删链接本身（os.rmdir 只删 junction，不删目标内容），再删整棵临时目录。
        for link in reversed(self.links):
            try:
                if os.name == "nt":
                    os.rmdir(str(link))
                else:
                    os.unlink(str(link))
            except OSError:
                pass
        shutil.rmtree(str(self.root), ignore_errors=True)

    def lock_unreadable(self, path):
        """让 path 读不出来：Windows 上以不共享的方式打开并持有句柄；POSIX 上去掉读权限（root 时跳过）。"""
        path = str(path)
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            create = kernel32.CreateFileW
            create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                               wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
            create.restype = wintypes.HANDLE
            close = kernel32.CloseHandle
            close.argtypes = [wintypes.HANDLE]
            close.restype = wintypes.BOOL
            generic_read, open_existing, normal = 0x80000000, 3, 0x80
            handle = create(path, generic_read, 0, None, open_existing, normal, None)  # 共享模式 0：别人打不开
            if not handle or handle == wintypes.HANDLE(-1).value:
                self.skipTest("无法独占打开 %s" % path)
            self.addCleanup(close, handle)
        else:
            if hasattr(os, "geteuid") and os.geteuid() == 0:
                self.skipTest("root 不受文件权限限制")
            os.chmod(path, 0)
            self.addCleanup(os.chmod, path, 0o600)
        try:
            with open(path, "rb"):
                pass
        except OSError:
            return
        self.skipTest("文件没有被锁住，无法构造不可读的夹具")

    def make_dir_link(self, link, target):
        link = Path(link)
        target = Path(target)
        target.mkdir(parents=True, exist_ok=True)
        link.parent.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            proc = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True)
            if proc.returncode != 0:
                self.skipTest("mklink /J 不可用")
        else:
            try:
                os.symlink(str(target), str(link), target_is_directory=True)
            except OSError:
                self.skipTest("符号链接不可用")
        self.links.append(link)
        self.assertTrue(pd.is_link_or_junction(link), "夹具链接没有被 is_link_or_junction 识别")

    def attempt(self, task, n, *, state="PASS", state_at=STATE_AT, plan_version=None, summary=None, files=None,
                events=None):
        d = self.runs / task / ("attempt-%03d" % n)
        d.mkdir(parents=True, exist_ok=True)
        if state is not None:
            put(d / "state.json", dump({"state": state, "at": state_at}))
        if plan_version is not None:
            put(d / "meta.json", dump({"task_id": task, "plan_version": plan_version, "attempt_no": n,
                                       "attempt_id": "%s-%03d" % (task, n)}))
        if summary is not None:
            put(d / "summary.md", summary)
        for rel, text in (files or {}).items():
            put(d / rel, text)
        if events is not None:
            put(d / "events-summary.json", events if isinstance(events, str) else dump(events))
        return d

    def jrun(self, argv):
        code, out, err = run_logs(list(argv) + ["--json"], self.repo)
        obj = json.loads(out) if code == 0 else None
        return code, obj, err

    def assertUsageError(self, argv, *, error_line=True):
        code, out, err = run_logs(argv, self.repo)
        self.assertEqual(code, 2, (argv, out, err))
        if error_line:
            self.assertIn("ERROR:", err, argv)
        self.assertNotIn("Traceback", err, argv)
        return out, err


# ---------------------------------------------------------------------------
# 基本用法、参数与错误（B0、B3、B6、B7、B9）
# ---------------------------------------------------------------------------

class Shape(OracleBase):
    def test_missing_runs_root_is_empty_not_an_error(self):
        code, out, err = run_logs(["list"], self.repo)
        self.assertEqual((code, "没有 attempt" in out), (0, True), (out, err))
        code, obj, _ = self.jrun(["list"])
        self.assertEqual(obj, {"attempts": [], "skipped_links": 0})
        code, obj, _ = self.jrun(["usage"])
        self.assertEqual(code, 0)
        self.assertEqual(obj["executor"]["totals"], five(0, 0, 0, 0, 0))
        self.assertEqual(obj["executor"]["counts"], {"known": 0, "partial": 0, "unknown": 0})
        self.assertEqual(obj["executor"]["by_model"], [])
        self.assertIsNone(obj["planner"])
        code, out, err = run_logs(["search", "x"], self.repo)
        self.assertEqual((code, match_lines(out)), (0, []), (out, err))
        # runs 存在但为空，结果相同
        self.runs.mkdir(parents=True)
        code, out, err = run_logs(["list"], self.repo)
        self.assertEqual((code, "没有 attempt" in out), (0, True), (out, err))
        code, obj, _ = self.jrun(["list"])
        self.assertEqual(obj, {"attempts": [], "skipped_links": 0})
        code, obj, _ = self.jrun(["usage"])
        self.assertEqual((code, obj["executor"]["totals"]), (0, five(0, 0, 0, 0, 0)))
        code, out, err = run_logs(["search", "x"], self.repo)
        self.assertEqual((code, match_lines(out)), (0, []), (out, err))

    def test_unknown_subcommand_and_bad_task_id_are_usage_errors(self):
        # 参数校验可以由 argparse 完成（没有 ERROR 行），也可以由命令完成；两种都是退出码 2。
        self.assertUsageError(["frobnicate"], error_line=False)
        self.assertUsageError(["list", "--task", "../x"], error_line=False)
        self.assertUsageError(["list", "--task", "Task-A"], error_line=False)
        self.assertUsageError(["list", "--state"], error_line=False)

    def test_search_bad_regex_and_max_are_usage_errors(self):
        self.assertUsageError(["search", "("], error_line=False)
        self.assertUsageError(["search", "x", "--max", "0"], error_line=False)
        self.assertUsageError(["search", "x", "--max", "abc"], error_line=False)

    def test_usage_time_arguments_need_timezone_and_order(self):
        self.assertUsageError(["usage", "--since", "2026-10-17T10:00:00"], error_line=False)
        self.assertUsageError(["usage", "--until", "2026-10-17"], error_line=False)
        self.assertUsageError(["usage", "--since", "not-a-time"], error_line=False)
        self.assertUsageError(["usage", "--since", UNTIL, "--until", SINCE], error_line=False)

    def test_usage_missing_transcript_is_usage_error_before_any_read(self):
        missing = self.root / "no-such.jsonl"
        self.assertUsageError(["usage", "--transcript", str(missing)])

    def test_not_a_git_repository_is_usage_error(self):
        plain = self.root / "plain"
        plain.mkdir()
        code, out, err = run_logs(["list"], plain)
        self.assertEqual(code, 2, (out, err))
        self.assertIn("ERROR:", err)
        self.assertNotIn("Traceback", err)

    def test_relative_explicit_path_resolves_against_cwd(self):
        self.attempt("task-a", 1, summary="REL-ONE\n")
        # 裸名 attempt-001 同时匹配 TASK_ID_RE，按 B5.2 先被当作任务名，找不到即退出码 2。
        self.assertUsageError(["show", "attempt-001"])
        old = os.getcwd()
        self.addCleanup(os.chdir, old)
        os.chdir(str(self.runs / "task-a"))
        code, obj, err = self.jrun(["show", "./attempt-001"])
        self.assertEqual((code, obj["attempt"], obj["summary"]["text"]), (0, "attempt-001", "REL-ONE\n"), err)

    def test_help_exits_zero(self):
        code, out, err = run_logs(["--help"], self.repo)
        self.assertEqual(code, 0, (out, err))


# ---------------------------------------------------------------------------
# 枚举与 list（B1、B2、B3、L8）
# ---------------------------------------------------------------------------

class Listing(OracleBase):
    def test_non_task_and_non_attempt_entries_are_ignored(self):
        self.attempt("task-a", 1)
        self.attempt("_tmp", 1)
        put(self.runs / "task-b" / "attempt-1" / "state.json", dump({"state": "PASS", "at": STATE_AT}))
        put(self.runs / "task-b" / "attempt-002", "not a directory")
        put(self.runs / "task-b" / "notes" / "x.txt", "x")
        put(self.runs / "readme.txt", "x")
        code, obj, err = self.jrun(["list"])
        self.assertEqual(code, 0, err)
        self.assertEqual([(r["task"], r["attempt"]) for r in obj["attempts"]], [("task-a", "attempt-001")])
        self.assertEqual(obj["skipped_links"], 0)

    def test_list_json_keys_numeric_order_and_recursive_evidence(self):
        self.attempt("task-a", 10, state="RUNNING", state_at="2026-10-17T10:05:00Z")
        self.attempt("task-a", 2, state="PASS", summary="hello\n",
                     files={"sub/x.txt": "abcd", "notes.txt": "12"})
        self.attempt("task-b", 1, state=None)  # 没有 state.json
        put(self.runs / "task-b" / "attempt-999" / "state.json", dump({"state": "DONE", "at": STATE_AT}))
        self.attempt("task-b", 1000, state="X")
        code, obj, err = self.jrun(["list"])
        self.assertEqual(code, 0, err)
        self.assertEqual(set(obj), {"attempts", "skipped_links"})
        order = [(r["task"], r["attempt"]) for r in obj["attempts"]]
        self.assertEqual(order, [("task-a", "attempt-002"), ("task-a", "attempt-010"),
                                 ("task-b", "attempt-001"), ("task-b", "attempt-999"),
                                 ("task-b", "attempt-1000")])
        row = obj["attempts"][0]
        self.assertEqual(set(row), {"task", "attempt", "state", "state_at", "evidence_files", "evidence_bytes",
                                    "has_summary"})
        self.assertEqual(row["state"], "PASS")
        self.assertEqual(row["state_at"], STATE_AT)
        self.assertEqual(row["evidence_files"], 4)  # state.json、summary.md、sub/x.txt、notes.txt
        expected_bytes = len(dump({"state": "PASS", "at": STATE_AT}).encode()) + 6 + 4 + 2
        self.assertEqual(row["evidence_bytes"], expected_bytes)
        self.assertTrue(row["has_summary"])
        self.assertEqual(obj["attempts"][1]["state_at"], "2026-10-17T10:05:00Z")
        self.assertFalse(obj["attempts"][2]["has_summary"])
        self.assertEqual(obj["attempts"][2]["state"], "UNKNOWN")
        self.assertIsNone(obj["attempts"][2]["state_at"])
        self.assertEqual(obj["attempts"][3]["state"], "DONE")

    def test_list_filters_task_and_exact_state(self):
        self.attempt("task-a", 1, state="PASS")
        self.attempt("task-a", 2, state="pass")
        self.attempt("task-b", 1, state="PASS")
        code, obj, _ = self.jrun(["list", "--task", "task-a", "--state", "PASS"])
        self.assertEqual([(r["task"], r["attempt"]) for r in obj["attempts"]], [("task-a", "attempt-001")])
        code, obj, _ = self.jrun(["list", "--task", "task-zzz"])
        self.assertEqual((code, obj["attempts"]), (0, []))

    def test_list_text_output_has_one_line_per_attempt(self):
        self.attempt("task-a", 1, state="PASS")
        self.attempt("task-a", 2, state="FAIL")
        code, out, err = run_logs(["list"], self.repo)
        self.assertEqual(code, 0, err)
        lines = [line for line in out.splitlines() if "task-a/attempt-00" in line]
        self.assertEqual(len(lines), 2, out)
        self.assertIn("PASS", lines[0])
        self.assertIn("FAIL", lines[1])


# ---------------------------------------------------------------------------
# show 与目标解析（B4、B5、L10、L13）
# ---------------------------------------------------------------------------

class Show(OracleBase):
    def setUp(self):
        super().setUp()
        self.attempt("task-a", 1, plan_version=1, summary="A1\n")
        self.attempt("task-a", 2, plan_version=2, summary="A2\n")
        self.attempt("task-a", 3, plan_version=1, summary="A3\n")

    def test_task_id_selects_the_newest_attempt(self):
        code, obj, err = self.jrun(["show", "task-a"])
        self.assertEqual((code, obj["attempt"], obj["summary"]["text"]), (0, "attempt-003", "A3\n"), err)

    def test_plan_key_selects_by_meta_plan_version(self):
        code, obj, _ = self.jrun(["show", "task-a.v1"])
        self.assertEqual((code, obj["attempt"]), (0, "attempt-003"))
        code, obj, _ = self.jrun(["show", "task-a.v2"])
        self.assertEqual((code, obj["attempt"]), (0, "attempt-002"))
        self.assertUsageError(["show", "task-a.v9"])

    def test_task_attempt_form_and_explicit_paths(self):
        code, obj, _ = self.jrun(["show", "task-a/attempt-001"])
        self.assertEqual((code, obj["summary"]["text"]), (0, "A1\n"))
        code, obj, _ = self.jrun(["show", str(self.runs / "task-a" / "attempt-002")])
        self.assertEqual((code, obj["attempt"], obj["summary"]["text"]), (0, "attempt-002", "A2\n"))
        dotdot = str(self.runs / "task-a" / "attempt-001" / ".." / "attempt-002")
        code, obj, err = self.jrun(["show", dotdot])
        self.assertEqual((code, obj["attempt"], obj["summary"]["text"]), (0, "attempt-002", "A2\n"), err)

    def test_targets_not_found_or_outside_runs_are_usage_errors(self):
        put(self.outside / "task-z" / "attempt-001" / "summary.md", "OUTSIDE-MARK\n")
        for target in ("task-zzz", "task-a.v9", "task-a/attempt-099", "_tmp", "",
                       "../outside/task-z/attempt-001", str(self.outside / "task-z" / "attempt-001"),
                       "task-a/attempt-001/extra", str(self.runs / "task-a"), str(self.runs)):
            out, err = self.assertUsageError(["show", target])
            self.assertNotIn("OUTSIDE-MARK", out + err, target)

    def test_nul_and_lone_surrogate_targets_are_usage_errors(self):
        self.assertUsageError(["show", "task-a\x00"])
        self.assertUsageError(["show", "task-a\ud800"])
        self.assertUsageError(["show", str(self.runs / "task-a" / "attempt-001") + "\x00"])

    def test_attempt_directory_name_must_match_the_pattern(self):
        self.attempt("_tmp", 1, summary="TMP-MARK\n")
        self.assertUsageError(["show", str(self.runs / "_tmp" / "attempt-001")])
        self.assertUsageError(["show", "_tmp/attempt-001"])

    def test_summary_truncated_at_65536_bytes_and_noted_in_text(self):
        big = "x" * 70000
        self.attempt("task-b", 1, summary=big)
        code, obj, err = self.jrun(["show", "task-b/attempt-001"])
        self.assertEqual(code, 0, err)
        self.assertEqual(set(obj["summary"]), {"bytes", "truncated", "text"})
        self.assertEqual(obj["summary"]["bytes"], 70000)
        self.assertTrue(obj["summary"]["truncated"])
        self.assertEqual(len(obj["summary"]["text"].encode("utf-8")), MAX_SUMMARY_BYTES)
        code, out, _ = run_logs(["show", "task-b/attempt-001"], self.repo)
        self.assertIn("已截断", out)
        self.assertIn("70000", out)

    def test_summary_of_exactly_65536_bytes_is_not_truncated(self):
        self.attempt("task-b", 2, summary="y" * MAX_SUMMARY_BYTES)
        code, obj, err = self.jrun(["show", "task-b/attempt-002"])
        self.assertEqual((code, obj["summary"]["truncated"], len(obj["summary"]["text"])),
                         (0, False, MAX_SUMMARY_BYTES), err)

    def test_summary_null_when_missing_and_evidence_listing(self):
        self.attempt("task-b", 1, files={"sub/x.txt": "xx", "z.log": "zzz"})
        code, obj, err = self.jrun(["show", "task-b/attempt-001"])
        self.assertEqual(code, 0, err)
        self.assertEqual(set(obj), {"task", "attempt", "state", "state_at", "summary", "evidence", "skipped_links"})
        self.assertIsNone(obj["summary"])
        self.assertEqual(obj["evidence"], [
            {"path": "state.json", "bytes": len(dump({"state": "PASS", "at": STATE_AT}).encode())},
            {"path": "sub/x.txt", "bytes": 2},
            {"path": "z.log", "bytes": 3},
        ])
        self.assertEqual(obj["skipped_links"], 0)

    def test_show_does_not_print_other_evidence_contents(self):
        self.attempt("task-b", 1, summary="S\n", files={"events-summary.json": dump({"x": "OTHER-MARK"}),
                                                        "notes.txt": "OTHER-MARK"})
        code, out, err = run_logs(["show", "task-b/attempt-001", "--json"], self.repo)
        self.assertEqual(code, 0, err)
        self.assertNotIn("OTHER-MARK", out)
        code, out, err = run_logs(["show", "task-b/attempt-001"], self.repo)
        self.assertNotIn("OTHER-MARK", out + err)

    def test_show_ignores_a_linked_newest_attempt_when_choosing_latest(self):
        shutil.rmtree(str(self.runs / "task-a" / "attempt-003"))
        self.make_dir_link(self.runs / "task-a" / "attempt-003", self.outside / "linked-a3")
        put(self.outside / "linked-a3" / "summary.md", "OUTSIDE-MARK\n")
        code, obj, err = self.jrun(["show", "task-a"])
        self.assertEqual((code, obj["attempt"], obj["summary"]["text"]), (0, "attempt-002", "A2\n"), err)
        # task.vN 同样跳过链接：版本 1 的两个 attempt 中，编号较大的 003 是链接，应当取 001
        code, obj, err = self.jrun(["show", "task-a.v1"])
        self.assertEqual((code, obj["attempt"], obj["summary"]["text"]), (0, "attempt-001", "A1\n"), err)


# ---------------------------------------------------------------------------
# 链接与平台（B1.3、B1.6、B5、B7.1、L12、L13、D10）
# ---------------------------------------------------------------------------

class Links(OracleBase):
    def setUp(self):
        super().setUp()
        self.attempt("task-a", 1, plan_version=1, summary="S1\n", files={"notes.txt": "nn"})
        self.attempt("task-a", 2, summary="S2\n")
        self.attempt("task-b", 1, summary="B1\n", state="PASS")

    def test_linked_task_directory_is_skipped_counted_and_not_followed(self):
        self.make_dir_link(self.runs / "task-l", self.outside / "task-l")
        put(self.outside / "task-l" / "attempt-001" / "state.json", dump({"state": "PASS", "at": STATE_AT}))
        put(self.outside / "task-l" / "attempt-001" / "summary.md", "LINKED-MARK\n")
        code, obj, err = self.jrun(["list"])
        self.assertEqual(code, 0, err)
        self.assertNotIn("task-l", [r["task"] for r in obj["attempts"]])
        self.assertEqual(obj["skipped_links"], 1)
        for argv in (["show", "task-l"], ["show", "task-l/attempt-001"],
                     ["show", str(self.runs / "task-l" / "attempt-001")]):
            out, err = self.assertUsageError(argv)
            self.assertNotIn("LINKED-MARK", out + err, argv)

    def test_linked_attempt_directory_is_skipped_and_counted(self):
        self.make_dir_link(self.runs / "task-a" / "attempt-003", self.outside / "linked-a3")
        put(self.outside / "linked-a3" / "state.json", dump({"state": "PASS", "at": STATE_AT}))
        code, obj, err = self.jrun(["list"])
        self.assertEqual(code, 0, err)
        self.assertNotIn(("task-a", "attempt-003"), [(r["task"], r["attempt"]) for r in obj["attempts"]])
        self.assertEqual(obj["skipped_links"], 1)
        out, err = self.assertUsageError(["show", "task-a/attempt-003"])
        out, err = self.assertUsageError(["show", str(self.runs / "task-a" / "attempt-003")])

    def test_linked_intermediate_directory_in_evidence_is_not_followed(self):
        self.make_dir_link(self.runs / "task-a" / "attempt-001" / "sub", self.outside / "evsub")
        put(self.outside / "evsub" / "secret.txt", "OUTSIDE-SUB-MARK")
        code, obj, err = self.jrun(["list", "--task", "task-a"])
        row = [r for r in obj["attempts"] if r["attempt"] == "attempt-001"][0]
        self.assertEqual(row["evidence_files"], 4)  # meta.json、notes.txt、state.json、summary.md
        self.assertEqual(obj["skipped_links"], 1)
        code, obj, err = self.jrun(["show", "task-a/attempt-001"])
        self.assertEqual(code, 0, err)
        self.assertEqual([e["path"] for e in obj["evidence"]],
                         ["meta.json", "notes.txt", "state.json", "summary.md"])
        self.assertEqual(obj["skipped_links"], 1)
        code, out, err = run_logs(["show", "task-a/attempt-001"], self.repo)
        self.assertNotIn("OUTSIDE-SUB-MARK", out + err)

    def test_link_named_like_summary_and_state_files_counts_as_missing(self):
        (self.runs / "task-a" / "attempt-002" / "summary.md").unlink()
        (self.runs / "task-b" / "attempt-001" / "state.json").unlink()
        self.make_dir_link(self.runs / "task-a" / "attempt-002" / "summary.md", self.outside / "sumlink")
        put(self.outside / "sumlink" / "x.txt", "OUTSIDE-SUM-MARK")
        self.make_dir_link(self.runs / "task-b" / "attempt-001" / "state.json", self.outside / "statelink")
        code, obj, err = self.jrun(["list"])
        self.assertEqual(code, 0, err)
        rows = {(r["task"], r["attempt"]): r for r in obj["attempts"]}
        self.assertFalse(rows[("task-a", "attempt-002")]["has_summary"])
        self.assertEqual(rows[("task-b", "attempt-001")]["state"], "UNKNOWN")
        self.assertIsNone(rows[("task-b", "attempt-001")]["state_at"])
        self.assertEqual(obj["skipped_links"], 2)
        code, obj, err = self.jrun(["show", "task-a/attempt-002"])
        self.assertIsNone(obj["summary"])
        self.assertEqual(obj["skipped_links"], 1)
        code, out, err = run_logs(["show", "task-a/attempt-002"], self.repo)
        self.assertNotIn("OUTSIDE-SUM-MARK", out + err)

    def test_usage_linked_events_summary_is_unknown_and_counted(self):
        self.make_dir_link(self.runs / "task-a" / "attempt-001" / "events-summary.json", self.outside / "evlink")
        put(self.outside / "evlink" / "x.txt", "x")
        self.attempt("task-b", 2, events=es_summary(five(1, 1, 1, 1, 4)))
        code, obj, err = self.jrun(["usage"])
        self.assertEqual(code, 0, err)
        rows = {(r["task"], r["attempt"]): r for r in obj["executor"]["attempts"]}
        self.assertEqual(rows[("task-a", "attempt-001")]["status"], "unknown")
        self.assertIsNone(rows[("task-a", "attempt-001")]["usage"])
        self.assertEqual(obj["executor"]["skipped_links"], 1)

    def test_link_then_dotdot_is_rejected_on_every_platform(self):
        # 名字 linked 是链接，随后被 `..` 抵消。段栈规则在压入时就检查它，两个平台都必须拒绝。
        self.make_dir_link(self.runs / "linked", self.outside / "sub")
        put(self.outside / "task-b" / "attempt-001" / "summary.md", "OUTSIDE-DOTDOT-MARK\n")
        put(self.outside / "task-b" / "attempt-001" / "state.json", dump({"state": "PASS", "at": STATE_AT}))
        target = str(self.runs / "linked" / ".." / "task-b" / "attempt-001")
        code, out, err = run_logs(["show", target, "--json"], self.repo)
        self.assertEqual(code, 2, (out, err))
        self.assertIn("ERROR:", err)
        self.assertNotIn("OUTSIDE-DOTDOT-MARK", out + err)

    def test_dotdot_between_normal_directories_is_accepted(self):
        # task-a 是普通目录，`..` 抵消它之后落到 task-b/attempt-001。
        target = str(self.runs / "task-a" / ".." / "task-b" / "attempt-001")
        code, obj, err = self.jrun(["show", target])
        self.assertEqual((code, obj["task"], obj["attempt"], obj["summary"]["text"]),
                         (0, "task-b", "attempt-001", "B1\n"), err)

    def test_dotdot_out_of_the_runs_root_is_rejected(self):
        # `..` 出栈越过 runs 根：必须退出码 2。runs/../task-b/attempt-001 若不检查出栈，会被当成 task-b/attempt-001。
        self.assertUsageError(["show", str(self.runs / ".." / "task-b" / "attempt-001")])
        # 最终位置仍在 runs 之内的写法同样拒绝（出栈越过 runs 根本身就是错误）。
        self.assertUsageError(["show", str(self.runs / ".." / "runs" / "task-b" / "attempt-001")])

    def test_link_in_the_middle_of_the_path_is_rejected(self):
        # task-a/attempt-001 存在；拒绝只能来自中间的链接 linkmid（它被 `..` 抵消）。
        self.make_dir_link(self.runs / "task-a" / "linkmid", self.outside / "mid")
        target = str(self.runs / "task-a" / "linkmid" / ".." / "attempt-001")
        self.assertUsageError(["show", target])

    def test_case_variant_of_the_runs_prefix_is_accepted_on_windows(self):
        if os.name != "nt":
            return  # 大小写不敏感只存在于 Windows；其它平台没有这一条写法。
        target = str(self.runs).upper() + os.sep + "task-a" + os.sep + "attempt-002"
        code, obj, err = self.jrun(["show", target])
        self.assertEqual((code, obj["attempt"], obj["summary"]["text"]), (0, "attempt-002", "S2\n"), err)

    def test_d11_predicate_comes_from_pi_dispatch_and_is_called(self):
        real = pd.is_link_or_junction

        def fake(path):
            text = str(path).replace("\\", "/")
            return text.endswith("task-a/attempt-002") or text.endswith("task-a/attempt-001/notes.txt") or real(path)

        with mock.patch.object(pd, "is_link_or_junction", side_effect=fake):
            code, obj, err = self.jrun(["list", "--task", "task-a"])
            self.assertEqual(code, 0, err)
            self.assertEqual([r["attempt"] for r in obj["attempts"]], ["attempt-001"])
            # attempt-001 的证据：meta.json、state.json、summary.md、notes.txt（被标为链接，不计入）
            self.assertEqual(obj["attempts"][0]["evidence_files"], 3)
            self.assertEqual(obj["skipped_links"], 2)
            code, obj, err = self.jrun(["show", "task-a/attempt-001"])
            self.assertEqual([e["path"] for e in obj["evidence"]], ["meta.json", "state.json", "summary.md"])
            self.assertEqual(obj["skipped_links"], 1)

    def test_does_not_reuse_resolve_run_dir_or_task_attempts(self):
        with mock.patch.object(pd, "resolve_run_dir", side_effect=AssertionError("resolve_run_dir")), \
                mock.patch.object(pd, "task_attempts", side_effect=AssertionError("task_attempts")):
            self.assertEqual(self.jrun(["list"])[0], 0)
            self.assertEqual(self.jrun(["show", "task-a"])[0], 0)
            self.assertEqual(self.jrun(["usage"])[0], 0)
            code, out, err = run_logs(["search", "S"], self.repo)
            self.assertEqual(code, 0, err)

    def test_source_has_no_direct_link_predicates_or_forbidden_reuse(self):
        source = (ROOT / "scripts" / "kit_logs.py").read_text(encoding="utf-8")
        for token in ("islink(", "is_symlink(", "isjunction(", "st_reparse_point",
                      "FILE_ATTRIBUTE_REPARSE_POINT", "os.walk(", "from pi_dispatch import",
                      "resolve_run_dir", "task_attempts"):
            self.assertNotIn(token, source, token)
        self.assertIn("import pi_dispatch as pd", source)


# ---------------------------------------------------------------------------
# search（B6、L10）
# ---------------------------------------------------------------------------

class Search(OracleBase):
    def setUp(self):
        super().setUp()
        self.attempt("task-a", 1, files={
            "summary.md": "alpha one\nbeta\nalpha two\n",
            "sub/log.txt": "alpha in sub\n",
            "data.bin": "alpha binary\n",
            "code.py": "alpha py\n",
            "events.jsonl": '{"x": "alpha json"}\n',
        })
        self.attempt("task-a", 2, files={"notes.MD": "alpha uppercase suffix\n"})
        self.attempt("task-b", 1, files={"summary.md": "alpha b\n"})

    def test_match_lines_format_order_and_relative_paths(self):
        code, out, err = run_logs(["search", "alpha"], self.repo)
        self.assertEqual(code, 0, err)
        self.assertEqual(match_lines(out), [
            ("task-a/attempt-001/events.jsonl", 1, '{"x": "alpha json"}'),
            ("task-a/attempt-001/sub/log.txt", 1, "alpha in sub"),
            ("task-a/attempt-001/summary.md", 1, "alpha one"),
            ("task-a/attempt-001/summary.md", 3, "alpha two"),
            ("task-b/attempt-001/summary.md", 1, "alpha b"),
        ], out)

    def test_task_filter_and_no_match(self):
        code, out, err = run_logs(["search", "alpha", "--task", "task-b"], self.repo)
        self.assertEqual(match_lines(out), [("task-b/attempt-001/summary.md", 1, "alpha b")], out)
        code, out, err = run_logs(["search", "zzz-no-such"], self.repo)
        self.assertEqual((code, match_lines(out)), (0, []))

    def test_default_max_is_fifty_and_truncation_is_noted(self):
        lines = "".join("hit %03d\n" % i for i in range(60))
        self.attempt("task-c", 1, files={"summary.md": lines})
        code, out, err = run_logs(["search", "hit", "--task", "task-c"], self.repo)
        self.assertEqual(code, 0, err)
        self.assertEqual(len(match_lines(out)), 50, out)
        notes = [line for line in out.splitlines() if not MATCH_RE.match(line)]
        self.assertTrue(any("50" in line for line in notes), out)
        code, out, err = run_logs(["search", "hit", "--task", "task-c", "--max", "5"], self.repo)
        self.assertEqual(len(match_lines(out)), 5, out)

    def test_exactly_max_matches_gives_no_truncation_note(self):
        lines = "".join("only %d\n" % i for i in range(50))
        self.attempt("task-d", 1, files={"summary.md": lines})
        code, out, err = run_logs(["search", "only", "--task", "task-d"], self.repo)
        self.assertEqual(len(match_lines(out)), 50)
        self.assertEqual([line for line in out.splitlines() if not MATCH_RE.match(line)], [], out)

    def test_long_line_is_cut_to_200_characters_but_still_matched(self):
        self.attempt("task-e", 1, files={"summary.md": "x" * 5000 + "NEEDLE-END\n"})
        code, out, err = run_logs(["search", "NEEDLE-END", "--task", "task-e"], self.repo)
        found = match_lines(out)
        self.assertEqual(len(found), 1, out)
        self.assertEqual(len(found[0][2]), 200)
        self.assertEqual(found[0][2], "x" * 200)

    def test_linked_entries_under_attempt_are_not_searched(self):
        self.make_dir_link(self.runs / "task-a" / "attempt-001" / "linkdir", self.outside / "searchlink")
        put(self.outside / "searchlink" / "x.txt", "alpha outside\n")
        code, out, err = run_logs(["search", "alpha outside"], self.repo)
        self.assertEqual(code, 0, err)
        self.assertEqual(match_lines(out), [], out)
        self.assertIn("跳过的链接：1", out)


# ---------------------------------------------------------------------------
# 执行端用量（B7.1、L7）
# ---------------------------------------------------------------------------

class ExecutorUsage(OracleBase):
    def setUp(self):
        super().setUp()
        self.attempt("task-a", 1, events=es_summary(five(100, 50, 10, 5, 165)))
        self.attempt("task-a", 2, events=es_summary(five(1, 2, 3, 4, 10), complete=False))
        self.attempt("task-a", 3, events=es_summary(five(10, 20, 30, 40, 100), truncated=True))
        self.attempt("task-a", 4, events=es_summary(five(1000, 2000, 3000, 4000, 10000), parse_error_lines=[7]))
        self.attempt("task-a", 5)  # 没有 events-summary.json
        self.attempt("task-a", 6, events=es_summary(use=5))
        self.attempt("task-a", 7, events=es_summary(use=None))
        self.attempt("task-a", 8, events=es_summary(use={"input": 1, "output": 1, "cacheRead": 1, "cacheWrite": 1}))
        self.attempt("task-a", 9, events="{not json")
        self.attempt("task-b", 1, events=es_summary(five(1, 1, 1, 1, 4),
                                                    requested={"provider": "step", "model": "other-1"}))

    def test_known_partial_unknown_statuses_and_totals(self):
        code, obj, err = self.jrun(["usage"])
        self.assertEqual(code, 0, err)
        ex = obj["executor"]
        self.assertEqual(set(ex), {"attempts", "totals", "counts", "by_model", "skipped_links"})
        status = {(r["task"], r["attempt"]): r["status"] for r in ex["attempts"]}
        self.assertEqual(status[("task-a", "attempt-001")], "known")
        self.assertEqual(status[("task-a", "attempt-002")], "partial")
        self.assertEqual(status[("task-a", "attempt-003")], "partial")
        self.assertEqual(status[("task-a", "attempt-004")], "partial")
        for n in (5, 6, 7, 8, 9):
            self.assertEqual(status[("task-a", "attempt-%03d" % n)], "unknown", n)
        self.assertEqual(ex["counts"], {"known": 2, "partial": 3, "unknown": 5})
        self.assertEqual(ex["totals"], five(1112, 2073, 3044, 4050, 10279))
        unknown_rows = [r for r in ex["attempts"] if r["status"] == "unknown"]
        self.assertTrue(all(r["usage"] is None for r in unknown_rows))
        self.assertEqual(ex["skipped_links"], 0)

    def test_by_model_groups_nulls_first_and_no_cost_key(self):
        code, obj, err = self.jrun(["usage"])
        groups = obj["executor"]["by_model"]
        self.assertEqual([g["requested_model"] for g in groups], [None, "bb/step-5-preview", "step/other-1"])
        self.assertEqual(set(groups[0]), {"requested_model", "known", "partial", "unknown", "usage"})
        self.assertEqual((groups[0]["known"], groups[0]["partial"], groups[0]["unknown"]), (0, 0, 2))
        self.assertEqual((groups[1]["known"], groups[1]["partial"], groups[1]["unknown"]), (1, 3, 3))
        self.assertEqual(groups[1]["usage"], five(1111, 2072, 3043, 4049, 10275))
        self.assertEqual(groups[2]["usage"], five(1, 1, 1, 1, 4))
        code, out, err = run_logs(["usage", "--json"], self.repo)
        self.assertEqual(code, 0, err)
        self.assertNotIn("cost", out.lower())

    def test_task_filter_limits_attempts_and_totals(self):
        code, obj, err = self.jrun(["usage", "--task", "task-b"])
        self.assertEqual(code, 0, err)
        self.assertEqual([(r["task"], r["attempt"]) for r in obj["executor"]["attempts"]],
                         [("task-b", "attempt-001")])
        self.assertEqual(obj["executor"]["totals"], five(1, 1, 1, 1, 4))
        self.assertEqual(obj["executor"]["counts"], {"known": 1, "partial": 0, "unknown": 0})

    def test_usage_attempt_rows_have_fixed_keys(self):
        code, obj, err = self.jrun(["usage", "--task", "task-a"])
        for row in obj["executor"]["attempts"]:
            self.assertEqual(set(row), {"task", "attempt", "requested_model", "status", "usage"})
            if row["usage"] is not None:
                self.assertEqual(set(row["usage"]), set(USAGE_KEYS))


# ---------------------------------------------------------------------------
# 规划端用量（B7.2、L1–L6、L11）
# ---------------------------------------------------------------------------

class PlannerUsage(OracleBase):
    def run_planner(self, *paths, since=None, until=None):
        argv = ["usage"]
        for p in paths:
            argv += ["--transcript", str(p)]
        if since is not None:
            argv += ["--since", since]
        if until is not None:
            argv += ["--until", until]
        code, obj, err = self.jrun(argv)
        self.assertEqual(code, 0, err)
        return obj["planner"]

    def test_l1_same_id_three_times_counts_once(self):
        path = self.root / "t1.jsonl"
        transcript(path, [rec("m1"), rec("m1"), rec("m1")])
        p = self.run_planner(path, since=SINCE, until=UNTIL)
        self.assertEqual(p["included_messages"], 1)
        self.assertEqual(p["by_model"], [{"model": "model-a", "sidechain": False, "messages": 1,
                                          "input_tokens": 10, "cache_creation_input_tokens": 2,
                                          "cache_read_input_tokens": 3, "output_tokens": 4}])
        self.assertEqual((p["duplicate_records"], p["conflict_ids"], p["conflict_records"]), (2, 0, 0))
        self.assertFalse(p["partial"])

    def test_l1_subagent_stream_counts_the_final_record_in_any_order(self):
        # 子代理写法：三条中间记录（output 8）加一条最终记录（output 800）。中间记录不计数；最终记录不一定在最后。
        stream = [interim("s1", sidechain=True), interim("s1", sidechain=True), interim("s1", sidechain=True),
                  rec("s1", sidechain=True, use=usage(o=800), stop="tool_use")]
        side_row = {"model": "model-a", "sidechain": True, "messages": 1, "input_tokens": 10,
                    "cache_creation_input_tokens": 2, "cache_read_input_tokens": 3, "output_tokens": 800}
        for order in itertools.permutations(range(4)):
            path = self.root / ("stream-%s.jsonl" % "".join(map(str, order)))
            transcript(path, [stream[i] for i in order])
            p = self.run_planner(path, since=SINCE, until=UNTIL)
            self.assertEqual(p["by_model"], [side_row], order)
            self.assertEqual((p["included_messages"], p["duplicate_records"], p["intermediate_records"],
                              p["partial"]), (1, 0, 3, False), order)
        # 同一 id 拆到两个文件，并交换文件顺序：结果相同
        fa, fb = self.root / "stream-a.jsonl", self.root / "stream-b.jsonl"
        transcript(fa, [stream[2], stream[0]])
        transcript(fb, [stream[3], stream[1]])
        forward = self.run_planner(fa, fb, since=SINCE, until=UNTIL)
        backward = self.run_planner(fb, fa, since=SINCE, until=UNTIL)
        self.assertEqual(forward, backward)
        self.assertEqual(forward["by_model"], [side_row])

    def test_l1_main_session_triple_and_max_tokens_final_are_counted(self):
        path = self.root / "t1-mixed.jsonl"
        transcript(path, [rec("m1"), rec("m1"), rec("m1"),
                          rec("x1", stop="max_tokens", use=usage(o=77))])
        p = self.run_planner(path, since=SINCE, until=UNTIL)
        self.assertEqual(p["by_model"], [{"model": "model-a", "sidechain": False, "messages": 2,
                                          "input_tokens": 20, "cache_creation_input_tokens": 4,
                                          "cache_read_input_tokens": 6, "output_tokens": 81}])
        self.assertEqual((p["included_messages"], p["duplicate_records"]), (2, 2))

    def test_l2_conflict_pairs_of_each_kind_and_number_normalisation(self):
        path = self.root / "t2.jsonl"
        transcript(path, [
            rec("p1"), rec("p1", use=usage(i=11)),
            rec("p2"), rec("p2", model="model-b"),
            rec("p3"), rec("p3", sidechain=True),
            rec("p4", use=usage(o=1)), rec("p4", use=usage(o=1.0)),
            rec("p5", use={"input_tokens": 10, "cache_creation_input_tokens": 2, "output_tokens": 4}),
            rec("p5", use={"input_tokens": 10, "cache_creation_input_tokens": 2, "cache_read_input_tokens": None,
                           "output_tokens": 4}),
        ])
        p = self.run_planner(path, since=SINCE, until=UNTIL)
        self.assertEqual((p["conflict_ids"], p["conflict_records"], p["duplicate_records"]), (5, 10, 0))
        self.assertEqual((p["included_messages"], p["by_model"]), (0, []))
        self.assertTrue(p["partial"])

    def test_l2_triple_a_a_b_is_one_conflict_of_three_records(self):
        path = self.root / "t2b.jsonl"
        transcript(path, [rec("q1"), rec("q1"), rec("q1", use=usage(o=9))])
        p = self.run_planner(path, since=SINCE, until=UNTIL)
        self.assertEqual((p["conflict_ids"], p["conflict_records"], p["duplicate_records"]), (1, 3, 0))
        self.assertTrue(p["partial"])

    def test_l2_stream_conflicts_between_finals_and_intermediates(self):
        path = self.root / "t2s-final.jsonl"
        transcript(path, [
            rec("f-cnt"), rec("f-cnt", use=usage(i=11)),          # 最终记录之间：四项计数不同
            rec("f-mod"), rec("f-mod", model="model-b"),          # 最终记录之间：model 不同
            rec("f-side"), rec("f-side", sidechain=True),         # 最终记录之间：isSidechain 不同
        ])
        p = self.run_planner(path, since=SINCE, until=UNTIL)
        self.assertEqual((p["conflict_ids"], p["conflict_records"], p["included_messages"]), (3, 6, 0))
        self.assertTrue(p["partial"])
        path = self.root / "t2s-interim.jsonl"
        transcript(path, [
            interim("i-mod", model="model-b"), rec("i-mod"),      # 中间记录的 model 与最终记录不同
            interim("i-side", sidechain=True), rec("i-side"),     # 中间记录的 model 相同，isSidechain 不同
        ])
        p = self.run_planner(path, since=SINCE, until=UNTIL)
        self.assertEqual((p["conflict_ids"], p["conflict_records"], p["incomplete_ids"]), (2, 4, 0))
        self.assertTrue(p["partial"])

    def test_l2_interim_only_group_is_incomplete_and_marks_partial(self):
        path = self.root / "t2s-incomplete.jsonl"
        transcript(path, [interim("inc1"), interim("inc1", use=usage(o=8))])
        p = self.run_planner(path, since=SINCE, until=UNTIL)
        self.assertEqual((p["incomplete_ids"], p["conflict_ids"], p["included_messages"],
                          p["intermediate_records"], p["duplicate_records"]), (1, 0, 0, 2, 0))
        self.assertTrue(p["partial"])
        # 没有最终记录时，组内中间记录的 model 彼此不同：同一 id 的记录不一致，记为冲突
        path = self.root / "t2s-incomplete-conflict.jsonl"
        transcript(path, [interim("inc2"), interim("inc2", model="model-b")])
        p = self.run_planner(path, since=SINCE, until=UNTIL)
        self.assertEqual((p["conflict_ids"], p["incomplete_ids"]), (1, 0))

    def test_empty_or_missing_stop_reason_is_intermediate(self):
        path = self.root / "t2s-empty.jsonl"
        transcript(path, [rec("e1"), rec("e1", stop=""), rec("k1"), rec("k1", stop=_OMIT)])
        p = self.run_planner(path, since=SINCE, until=UNTIL)
        self.assertEqual((p["intermediate_records"], p["duplicate_records"], p["included_messages"],
                          p["conflict_ids"], p["incomplete_ids"]), (2, 0, 2, 0, 0))

    def test_l2_fixed_block_of_five_classes_and_non_integer_field(self):
        path = self.root / "t2c.jsonl"
        transcript(path, [
            rec("c1"), rec("c1", use=usage(i=99)),                # 冲突（最终记录之间计数不同）
            interim("i1"),                                        # 未完成（只有中间记录）
            rec("t1", ts="not-a-time"), rec("t1", ts="2026-10-17T10:15:00"),  # 无可用时间（两条都不可用）
            rec("o1", ts=UNTIL),                                  # 窗口外（恰好等于 until）
            rec("n1", use=usage(o=None)), rec("n1", use=usage(o=None)),       # 计入，output 为 null
            interim("n1", use=usage(o=8)),                        # 中间记录：不计数
        ])
        p = self.run_planner(path, since=SINCE, until=UNTIL)
        self.assertEqual(p["conflict_ids"], 1)
        self.assertEqual(p["incomplete_ids"], 1)
        self.assertEqual(p["ids_without_time"], 1)
        self.assertEqual(p["outside_window_ids"], 1)
        self.assertEqual(p["included_messages"], 1)
        self.assertEqual(p["non_integer_fields"], 1)
        self.assertEqual(p["unusable_timestamps"], 2)
        self.assertEqual(p["conflict_records"], 2)
        self.assertEqual(p["duplicate_records"], 2)    # t1 与 n1 的最终记录各多一条
        self.assertEqual(p["intermediate_records"], 2)  # i1 与 n1 各一条中间记录
        self.assertTrue(p["partial"])

    def test_l3_bad_lines_non_candidates_and_non_integer_values(self):
        path = self.root / "t3.jsonl"
        transcript(path, [
            Raw("{bad json"),
            Raw(""), Raw("   "), Raw("\t"),  # 空行与只含空白的行：直接忽略，不计入任何计数
            Raw('"just a string"'), Raw("[1, 2]"), Raw("5"),
            {"timestamp": IN_WINDOW, "message": "not-an-object"},
            {"timestamp": IN_WINDOW, "message": {"id": 5, "usage": usage()}},
            {"timestamp": IN_WINDOW, "message": {"id": "", "usage": usage()}},
            {"timestamp": IN_WINDOW, "message": {"id": "nou"}},
            {"timestamp": IN_WINDOW, "message": {"id": "x1", "usage": 5}},
            rec("f1", use={"input_tokens": "12", "cache_creation_input_tokens": 2,
                           "cache_read_input_tokens": 3, "output_tokens": 4}),
            rec("f2", use=usage(o=True)),
            rec("f3", use=usage(r=1.5)),
            rec("f4", use={"input_tokens": 10, "cache_read_input_tokens": 3, "output_tokens": 4}),
            rec("f5", use={"input_tokens": None, "cache_creation_input_tokens": [1],
                           "cache_read_input_tokens": {"a": 1}, "output_tokens": "5"}),
        ])
        p = self.run_planner(path, since=SINCE, until=UNTIL)
        self.assertEqual(p["skipped_lines"], {"bad_json": 1, "not_object": 3, "not_candidate": 5})
        self.assertEqual(p["included_messages"], 5)
        self.assertEqual(p["non_integer_fields"], 8)
        self.assertFalse(p["partial"])

    def test_l4_order_independence_across_files_and_records(self):
        f1 = self.root / "order-1.jsonl"
        f2 = self.root / "order-2.jsonl"
        lines1 = [
            rec("w1", ts="2026-10-17T09:59:59Z"),
            rec("w2", ts=SINCE),
            rec("w4", ts="2026-10-17T10:29:59.999999Z"),
        ]
        lines2 = [
            rec("w1", ts=SINCE),
            rec("w3", ts=UNTIL),
            rec("w4", ts="2026-10-17T10:45:00Z"),
            rec("w5", ts="2026-10-17T18:00:00+08:00"),
            rec("w2", ts="2026-10-17T10:00:00Z"),
        ]
        transcript(f1, lines1)
        transcript(f2, lines2)
        canonical = self.run_planner(f1, f2, since=SINCE, until=UNTIL)
        self.assertEqual(canonical["included_messages"], 3)
        self.assertEqual(canonical["outside_window_ids"], 2)
        self.assertEqual(canonical["duplicate_records"], 3)
        self.assertEqual(canonical["by_model"][0]["messages"], 3)
        self.assertEqual(canonical["by_model"][0]["input_tokens"], 30)
        rng = random.Random(20261017)
        combined = [(f1, row) for row in lines1] + [(f2, row) for row in lines2]
        for trial in range(30):
            shuffled = list(combined)
            rng.shuffle(shuffled)
            paths = [f1, f2] if trial % 2 == 0 else [f2, f1]
            files = {f1: [], f2: []}
            for path, row in shuffled:
                files[path].append(row)
            for path in files:
                transcript(path, files[path])
            self.assertEqual(self.run_planner(*paths, since=SINCE, until=UNTIL), canonical, trial)

    def test_l4_window_bounds_are_since_inclusive_until_exclusive(self):
        path = self.root / "t4.jsonl"
        transcript(path, [
            rec("b1", ts=SINCE),
            rec("b2", ts=UNTIL),
            rec("b3", ts="2026-10-17T10:29:59.999999Z"),
            rec("b4", ts="2026-10-17T09:59:59Z"),
            rec("b5", ts="2026-10-17T09:59:59Z"), rec("b5", ts=SINCE),
        ])
        p = self.run_planner(path, since=SINCE, until=UNTIL)
        self.assertEqual(p["included_messages"], 2)  # b1、b3
        self.assertEqual(p["outside_window_ids"], 3)  # b2、b4、b5（取最小可用时间）
        self.assertEqual(p["duplicate_records"], 1)

    def test_l5_timestamp_forms_and_naive_times_are_unusable_not_local(self):
        path = self.root / "t5.jsonl"
        transcript(path, [
            rec("lt1", ts="2026-10-17T10:15:00Z"),
            rec("lt1", ts="2026-10-17T09:00:00"),  # 不带时区：不可用；若按 UTC 看会落在窗口之前
            rec("lt2", ts="2026/10/17 10:15"),
            rec("lt3", ts=1792321700),
            rec("lt4", ts="2026-10-17T18:15:00+08:00"),
            rec("lt5", ts="2026-10-17T10:15:00.123Z"),
        ])
        p = self.run_planner(path, since=SINCE, until=UNTIL)
        self.assertEqual(p["unusable_timestamps"], 3)
        self.assertEqual(p["ids_without_time"], 2)
        self.assertEqual(p["included_messages"], 3)
        self.assertEqual(p["outside_window_ids"], 0)
        self.assertEqual(p["duplicate_records"], 1)

    def test_l5_cli_times_need_timezone(self):
        path = self.root / "t5b.jsonl"
        transcript(path, [rec("z1")])
        self.assertUsageError(["usage", "--transcript", str(path), "--since", "2026-10-17T10:00:00"],
                              error_line=False)
        self.assertUsageError(["usage", "--transcript", str(path), "--until", "2026-10-17T10:30:00"],
                              error_line=False)

    def test_l6_sidechain_grouped_apart_from_main_thread_and_normalised(self):
        path = self.root / "t6.jsonl"
        raw = rec("sc3")
        raw["isSidechain"] = "true"  # 字符串不算 true
        transcript(path, [rec("sc1"), rec("sc2", sidechain=True, use=usage(i=1, c=1, r=1, o=1)), raw,
                          rec("sc4", model=5)])
        p = self.run_planner(path, since=SINCE, until=UNTIL)
        self.assertEqual([(g["model"], g["sidechain"], g["messages"]) for g in p["by_model"]],
                         [(None, False, 1), ("model-a", False, 2), ("model-a", True, 1)])
        side = [g for g in p["by_model"] if g["sidechain"]][0]
        self.assertEqual(side["input_tokens"], 1)

    def test_directory_argument_reads_direct_jsonl_children_only(self):
        d = self.root / "transcripts"
        transcript(d / "a.jsonl", [rec("d1")])
        transcript(d / "sub" / "b.jsonl", [rec("d2")])
        transcript(d / "c.txt", [rec("d3")])
        self.make_dir_link(d / "link.jsonl", self.outside / "tlink")
        transcript(self.outside / "tlink" / "x.jsonl", [rec("d4")])
        p = self.run_planner(d, since=SINCE, until=UNTIL)
        self.assertEqual(p["included_messages"], 1)
        self.assertEqual(p["skipped_links"], 1)
        self.assertEqual(p["by_model"][0]["messages"], 1)

    def test_transcript_content_and_secret_like_text_are_never_printed(self):
        path = self.root / "t11.jsonl"
        transcript(path, [rec("s1"), rec("s2", model="model-b")])
        code, out, err = run_logs(["usage", "--transcript", str(path), "--since", SINCE, "--until", UNTIL, "--json"],
                                  self.repo)
        self.assertEqual(code, 0, err)
        self.assertNotIn("SYNTHETIC", out + err)
        self.assertNotIn("sk-ant", out + err)
        code, out, err = run_logs(["usage", "--transcript", str(path), "--since", SINCE, "--until", UNTIL], self.repo)
        self.assertNotIn("SYNTHETIC", out + err)
        self.assertNotIn("sk-ant", out + err)

    def test_planner_null_without_transcript_and_partial_rules(self):
        code, obj, err = self.jrun(["usage"])
        self.assertIsNone(obj["planner"])
        path = self.root / "t-bad-only.jsonl"
        transcript(path, [Raw("{bad"), rec("ok1")])
        p = self.run_planner(path, since=SINCE, until=UNTIL)
        self.assertFalse(p["partial"])  # 只有坏行：不标部分
        self.assertTrue(p["lower_bound"])
        self.assertEqual(set(p), {"lower_bound", "partial", "included_messages", "by_model", "skipped_lines",
                                  "skipped_links", "unreadable_files", "duplicate_records", "conflict_ids",
                                  "conflict_records", "incomplete_ids", "intermediate_records",
                                  "unusable_timestamps", "ids_without_time", "outside_window_ids",
                                  "non_integer_fields"})
        incomplete = self.root / "t-incomplete.jsonl"
        transcript(incomplete, [interim("p-inc")])
        self.assertTrue(self.run_planner(incomplete, since=SINCE, until=UNTIL)["partial"])  # 未完成：标部分

    def test_unreadable_transcript_is_dropped_counted_and_marks_partial(self):
        good = self.root / "readable.jsonl"
        transcript(good, [rec("u1")])
        locked = self.root / "locked.jsonl"
        transcript(locked, [rec("u2"), rec("u3")])
        self.lock_unreadable(locked)
        p = self.run_planner(good, locked, since=SINCE, until=UNTIL)
        self.assertEqual(p["unreadable_files"], 1)
        self.assertEqual(p["included_messages"], 1)  # 只有 u1；locked 整个文件不计入
        self.assertTrue(p["partial"])


# ---------------------------------------------------------------------------
# 只读（L9）与输出上限（L10）
# ---------------------------------------------------------------------------

class ReadOnly(OracleBase):
    def test_every_subcommand_leaves_agent_dir_byte_identical(self):
        self.attempt("task-a", 1, plan_version=1, summary="one alpha\n",
                     files={"notes.txt": "alpha\n"}, events=es_summary(five(1, 2, 3, 4, 10)))
        self.attempt("task-a", 2, state=None, summary=None)
        transcript(self.outside / "session.jsonl", [rec("r1"), Raw("{bad")])
        before = snapshot(self.repo / ".agent")
        argvs = [
            ["list"], ["list", "--json"], ["list", "--task", "task-a", "--state", "PASS"],
            ["show", "task-a"], ["show", "task-a.v1", "--json"], ["show", str(self.runs / "task-a" / "attempt-001")],
            ["search", "alpha"], ["search", "("], ["search", "alpha", "--max", "1"],
            ["usage"], ["usage", "--json"],
            ["usage", "--transcript", str(self.outside / "session.jsonl"), "--since", SINCE, "--until", UNTIL, "--json"],
            ["show", "nothing-here"], ["list", "--task", "bad id"],
        ]
        for argv in argvs:
            run_logs(argv, self.repo)
        self.assertEqual(snapshot(self.repo / ".agent"), before)

    def test_summary_and_search_output_are_bounded_on_large_evidence(self):
        self.attempt("task-big", 1, summary="s" * 70000,
                     files={"log.txt": "".join("row %d needle\n" % i for i in range(1000))})
        code, out, err = run_logs(["search", "needle", "--task", "task-big"], self.repo)
        self.assertEqual(code, 0, err)
        self.assertEqual(len(match_lines(out)), 50)
        self.assertLess(len(out), 50 * 300)
        code, out, err = run_logs(["show", "task-big/attempt-001"], self.repo)
        self.assertLess(len(out), 70000)


# ---------------------------------------------------------------------------
# 文件级链接（规划端补测，kit-logs a001 复审：变异 M18 漏掉）
# ---------------------------------------------------------------------------

class FileLevelLinks(OracleBase):
    """读取前必须对证据文件本身做链接检查（合同 B1、B2、B4、B7.1；设计 D2）。

    能在测试里建出的链接（符号链接、junction）用 lstat 看都不是普通文件，“只读普通文件”这一步就会挡住，
    去掉链接检查也测不出来（kit-logs a001 的变异 M18）。所以这里用替身让 pi_dispatch.is_link_or_junction
    把一个普通文件当成链接：文件内容合法，只差“是链接”这一处。每个用例先在没有替身时确认同一份内容
    确实会被读出来，所以被测结果只能来自链接检查。
    """

    def fake_links(self, *names):
        """让 attempt 目录里名为 names 之一的普通文件被判为链接，其余路径照常判断。"""
        real = pd.is_link_or_junction
        wanted = set(names)

        def fake(path):
            p = Path(str(path))
            if p.name in wanted and self.runs in p.parents and p.is_file():
                return True
            return real(path)

        return mock.patch.object(pd, "is_link_or_junction", side_effect=fake)

    def test_state_json_link_is_not_read(self):
        self.attempt("task-a", 1, state="PASS")
        code, obj, err = self.jrun(["list"])
        self.assertEqual(code, 0, err)
        self.assertEqual((obj["attempts"][0]["state"], obj["attempts"][0]["state_at"]), ("PASS", STATE_AT))
        with self.fake_links("state.json"):
            code, obj, err = self.jrun(["list"])
        self.assertEqual(code, 0, err)
        self.assertEqual((obj["attempts"][0]["state"], obj["attempts"][0]["state_at"]), ("UNKNOWN", None))

    def test_summary_md_link_is_not_read(self):
        self.attempt("task-a", 1, summary="# 摘要\n内容\n")
        code, obj, err = self.jrun(["show", "task-a"])
        self.assertEqual(code, 0, err)
        self.assertIsNotNone(obj["summary"])
        with self.fake_links("summary.md"):
            code, obj, err = self.jrun(["show", "task-a"])
            self.assertEqual(code, 0, err)
            self.assertIsNone(obj["summary"])
            code, listed, err = self.jrun(["list"])
        self.assertEqual(code, 0, err)
        self.assertFalse(listed["attempts"][0]["has_summary"])

    def test_events_summary_link_is_unknown_and_counted(self):
        events = {"usage": {"input": 1, "output": 2, "cacheRead": 3, "cacheWrite": 4, "totalTokens": 10},
                  "requested_model": MODEL_OBJ, "complete": True, "truncated": False, "parse_error_lines": []}
        self.attempt("task-a", 1, events=events)
        code, obj, err = self.jrun(["usage"])
        self.assertEqual(code, 0, err)
        self.assertEqual(obj["executor"]["counts"]["known"], 1)
        with self.fake_links("events-summary.json"):
            code, obj, err = self.jrun(["usage"])
        self.assertEqual(code, 0, err)
        self.assertEqual((obj["executor"]["counts"]["known"], obj["executor"]["counts"]["unknown"]), (0, 1))
        self.assertEqual(obj["executor"]["attempts"][0]["usage"], None)
        self.assertGreaterEqual(obj["executor"]["skipped_links"], 1)

    def test_meta_json_link_is_not_used_for_plan_version(self):
        self.attempt("task-a", 1, plan_version=2)
        code, obj, err = self.jrun(["show", "task-a.v2"])
        self.assertEqual((code, obj["attempt"] if obj else None), (0, "attempt-001"), err)
        with self.fake_links("meta.json"):
            self.assertUsageError(["show", "task-a.v2"])


class ReworkV2(OracleBase):
    """kit-logs 复审 attempt-001（REVISE）的 F1、F2、F3 用例（对应合同 kit-logs.v2）。

    F1（B5.5 兜底）：形式 A、B、C 的目标目录也要过 pd.is_within(resolve)。用例把 pd.is_link_or_junction
        替身成“永远不是链接”，于是只剩兜底能拒绝 runs/task-x（指向外部的 junction）。
    F2（异常不得冒出，B0.5、B6、B7.2.5）：正则溢出与深嵌套、时间换算溢出、深嵌套 JSON。
    F3（列举失败按层处理，B0.5、B5.6、B9）：runs 根退出码 1；目标解析中找不到（退出码 2）；其余目录跳过且不计数；
        --transcript 目录列不出来计入 unreadable_files 并标部分。

    每个用例都断言 stderr 不含 Traceback；异常冒出时以用例失败报告（不是测试框架的 ERROR）。
    """

    OUTSIDE_MARK = "F1-OUTSIDE-MARK"
    CONTROL_MARK = "F1-CONTROL-MARK"
    OVERFLOW_TS = "0001-01-01T00:30:00+01:00"
    DEEP = "[" * 100000 + "]" * 100000

    def run_checked(self, argv):
        """运行一条命令：异常冒出即按用例失败；stderr 不得含 Traceback。"""
        try:
            code, out, err = run_logs(list(argv), self.repo)
        except Exception as exc:  # 异常冒出 = 堆栈输出，按用例失败报告
            self.fail("异常冒出（应退出码 0 或 2，不得冒出堆栈）：%s: %s；命令 %r" % (type(exc).__name__, exc, list(argv)))
        self.assertNotIn("Traceback", err, argv)
        return code, out, err

    def json_checked(self, argv):
        code, out, err = self.run_checked(list(argv) + ["--json"])
        return code, (json.loads(out) if code == 0 else None), err

    @staticmethod
    def has_error_line(err):
        return any(line.startswith("ERROR:") for line in err.splitlines())

    def write_attempt_files(self, base, task, marker):
        attempt = base / "attempt-001"
        put(attempt / "summary.md", marker + "\n")
        put(attempt / "state.json", dump({"state": "PASS", "at": STATE_AT}))
        put(attempt / "meta.json", dump({"task_id": task, "plan_version": 1, "attempt_no": 1,
                                         "attempt_id": task + "-001"}))

    @contextlib.contextmanager
    def unlistable(self, *directories):
        """让这些目录列不出来：os.listdir、os.scandir 与 Path.iterdir 都抛 PermissionError；其余路径照常。"""
        import pathlib
        blocked = {os.path.normcase(os.path.abspath(str(d))) for d in directories}

        def denied(path):
            return os.path.normcase(os.path.abspath(str(path))) in blocked

        def guard(real):
            def guarded(path=".", *args, **kwargs):
                if denied(path):
                    raise PermissionError(13, "列目录被拒绝（替身）", str(path))
                return real(path, *args, **kwargs)
            return guarded

        real_iterdir = pathlib.Path.iterdir

        def guarded_iterdir(path_self):
            if denied(path_self):
                raise PermissionError(13, "列目录被拒绝（替身）", str(path_self))
            return real_iterdir(path_self)

        with mock.patch.object(os, "listdir", guard(os.listdir)), \
                mock.patch.object(os, "scandir", guard(os.scandir)), \
                mock.patch.object(pathlib.Path, "iterdir", guarded_iterdir):
            yield

    # ---- F1：B5.5 兜底（所有形式都要过 is_within(resolve)） ----

    def test_f1_junction_target_is_rejected_when_the_link_check_is_stubbed_out(self):
        self.write_attempt_files(self.outside / "xdir", "task-x", self.OUTSIDE_MARK)
        self.make_dir_link(self.runs / "task-x", self.outside / "xdir")
        with mock.patch.object(pd, "is_link_or_junction", return_value=False):
            for target in ("task-x", "task-x.v1", "task-x/attempt-001"):
                code, out, err = self.run_checked(["show", target])
                self.assertEqual(code, 2, (target, out, err))
                self.assertNotIn(self.OUTSIDE_MARK, out + err, target)

    def test_f1_same_content_in_a_normal_directory_is_accepted_under_the_same_stub(self):
        self.write_attempt_files(self.runs / "task-y", "task-y", self.CONTROL_MARK)
        with mock.patch.object(pd, "is_link_or_junction", return_value=False):
            for target in ("task-y", "task-y.v1", "task-y/attempt-001"):
                code, out, err = self.run_checked(["show", target])
                self.assertEqual(code, 0, (target, out, err))
                self.assertIn(self.CONTROL_MARK, out, target)

    def test_f1_junction_target_is_rejected_by_the_link_check_without_the_stub(self):
        # 对照：没有替身时，链接检查本身就能拒绝（这条在候选上应当通过，它区分不了兜底是否存在）。
        self.write_attempt_files(self.outside / "xdir", "task-x", self.OUTSIDE_MARK)
        self.make_dir_link(self.runs / "task-x", self.outside / "xdir")
        for target in ("task-x", "task-x.v1", "task-x/attempt-001"):
            code, out, err = self.run_checked(["show", target])
            self.assertEqual(code, 2, (target, out, err))
            self.assertNotIn(self.OUTSIDE_MARK, out + err, target)

    # ---- F2：异常不得冒出堆栈（B0.5、B6、B7.2.5） ----

    def test_f2_overflowing_repetition_in_search_pattern_is_a_usage_error(self):
        self.attempt("task-a", 1, summary="a\n")
        code, out, err = self.run_checked(["search", "a{4294967296}"])
        self.assertEqual(code, 2, (out, err))
        self.assertTrue(self.has_error_line(err), err)

    def test_f2_deeply_nested_search_pattern_is_a_usage_error(self):
        self.attempt("task-a", 1, summary="a\n")
        code, out, err = self.run_checked(["search", "(" * 100000 + ")" * 100000])
        self.assertEqual(code, 2, (out, err))
        self.assertTrue(self.has_error_line(err), err)

    def test_f2_overflowing_timestamp_is_unusable_not_a_crash(self):
        path = self.root / "overflow.jsonl"
        transcript(path, [rec("ov1", ts=self.OVERFLOW_TS), rec("ov2", ts=self.OVERFLOW_TS), rec("ov2")])
        code, obj, err = self.json_checked(["usage", "--transcript", str(path), "--since", SINCE, "--until", UNTIL])
        self.assertEqual(code, 0, err)
        planner = obj["planner"]
        self.assertEqual(planner["unusable_timestamps"], 2)  # ov1 与 ov2 的溢出记录
        self.assertEqual(planner["ids_without_time"], 1)     # ov1 组内没有其它可用时间
        self.assertEqual(planner["included_messages"], 1)    # ov2 由带可用时间的那条代表
        self.assertEqual(planner["duplicate_records"], 1)

    def test_f2_overflowing_since_is_a_usage_error(self):
        path = self.root / "since.jsonl"
        transcript(path, [rec("s1")])
        code, out, err = self.run_checked(["usage", "--transcript", str(path), "--since", self.OVERFLOW_TS])
        self.assertEqual(code, 2, (out, err))

    def test_f2_deeply_nested_transcript_line_is_bad_json(self):
        path = self.root / "deep-line.jsonl"
        transcript(path, [rec("d1"), Raw(self.DEEP)])
        code, obj, err = self.json_checked(["usage", "--transcript", str(path), "--since", SINCE, "--until", UNTIL])
        self.assertEqual(code, 0, err)
        self.assertEqual(obj["planner"]["skipped_lines"], {"bad_json": 1, "not_object": 0, "not_candidate": 0})
        self.assertEqual(obj["planner"]["included_messages"], 1)

    def test_f2_deeply_nested_state_json_gives_unknown_state(self):
        self.attempt("task-a", 1, state=None, files={"state.json": self.DEEP})
        code, obj, err = self.json_checked(["list"])
        self.assertEqual(code, 0, err)
        self.assertEqual((obj["attempts"][0]["state"], obj["attempts"][0]["state_at"]), ("UNKNOWN", None))

    def test_f2_deeply_nested_events_summary_makes_the_attempt_unknown(self):
        self.attempt("task-a", 1, events=self.DEEP)
        code, obj, err = self.json_checked(["usage", "--task", "task-a"])
        self.assertEqual(code, 0, err)
        self.assertEqual(obj["executor"]["attempts"][0]["status"], "unknown")
        self.assertEqual(obj["executor"]["counts"]["unknown"], 1)

    def test_f2_deeply_nested_meta_json_is_a_non_match_for_plan_version(self):
        self.attempt("task-d", 1, plan_version=1, summary="ok\n")
        self.attempt("task-d", 2, files={"meta.json": self.DEEP})
        code, obj, err = self.json_checked(["show", "task-d.v1"])
        self.assertEqual((code, obj["attempt"]), (0, "attempt-001"), err)
        self.attempt("task-e", 1, files={"meta.json": self.DEEP})
        code, out, err = self.run_checked(["show", "task-e.v1"])
        self.assertEqual(code, 2, (out, err))

    # ---- F3：列举失败按层处理（B0.5、B5.6、B9） ----

    def test_f3_runs_root_unlistable_is_exit_1_with_one_error_line(self):
        self.attempt("task-a", 1, summary="a\n")
        with self.unlistable(self.runs):
            code, out, err = self.run_checked(["list"])
        self.assertEqual(code, 1, (out, err))
        self.assertTrue(self.has_error_line(err), err)

    def test_f3_task_directory_unlistable_is_skipped_and_show_is_usage_error(self):
        self.attempt("task-a", 1, summary="A\n")
        self.attempt("task-b", 1, summary="B\n")
        with self.unlistable(self.runs / "task-a"):
            code, obj, err = self.json_checked(["list"])
            self.assertEqual(code, 0, err)
            self.assertEqual({row["task"] for row in obj["attempts"]}, {"task-b"})
            self.assertEqual(obj["skipped_links"], 0)  # 列不出来不是链接，不计入跳过的链接
            code, out, err = self.run_checked(["show", "task-a"])
            self.assertEqual(code, 2, (out, err))

    def test_f3_attempt_directory_unlistable_is_skipped_and_its_own_show_is_usage_error(self):
        self.attempt("task-a", 1, summary="A1\n")
        self.attempt("task-a", 2, summary="A2\n")
        with self.unlistable(self.runs / "task-a" / "attempt-002"):
            code, obj, err = self.json_checked(["list"])
            self.assertEqual(code, 0, err)
            self.assertEqual([(row["task"], row["attempt"]) for row in obj["attempts"]], [("task-a", "attempt-001")])
            code, out, err = self.run_checked(["show", "task-a/attempt-002"])
            self.assertEqual(code, 2, (out, err))

    def test_f3_evidence_subdirectory_unlistable_is_not_counted_and_the_rest_is(self):
        self.attempt("task-a", 1, summary="S\n", files={"notes.txt": "nn", "sub/x.txt": "xyz"})
        state_bytes = len(dump({"state": "PASS", "at": STATE_AT}).encode("utf-8"))
        with self.unlistable(self.runs / "task-a" / "attempt-001" / "sub"):
            code, obj, err = self.json_checked(["list"])
            self.assertEqual(code, 0, err)
            row = obj["attempts"][0]
            self.assertEqual(row["evidence_files"], 3)  # notes.txt、state.json、summary.md
            self.assertEqual(row["evidence_bytes"], 2 + state_bytes + 2)
            code, shown, err = self.json_checked(["show", "task-a/attempt-001"])
            self.assertEqual(code, 0, err)
            self.assertEqual([item["path"] for item in shown["evidence"]],
                             ["notes.txt", "state.json", "summary.md"])
            self.assertEqual(shown["skipped_links"], 0)

    def test_f3_transcript_directory_unlistable_counts_unreadable_and_marks_partial(self):
        directory = self.root / "transcripts"
        transcript(directory / "a.jsonl", [rec("u1")])
        readable = self.root / "readable.jsonl"
        transcript(readable, [rec("u2")])
        argv = ["usage", "--transcript", str(directory), "--transcript", str(readable),
                "--since", SINCE, "--until", UNTIL]
        with self.unlistable(directory):
            code, obj, err = self.json_checked(argv)
        self.assertEqual(code, 0, err)
        self.assertEqual(obj["planner"]["unreadable_files"], 1)
        self.assertTrue(obj["planner"]["partial"])
        self.assertEqual(obj["planner"]["included_messages"], 1)  # 只有 readable.jsonl 的 u2

    def test_f3_transcript_directory_readable_control(self):
        directory = self.root / "transcripts"
        transcript(directory / "a.jsonl", [rec("u1")])
        code, obj, err = self.json_checked(["usage", "--transcript", str(directory), "--since", SINCE,
                                            "--until", UNTIL])
        self.assertEqual(code, 0, err)
        self.assertEqual((obj["planner"]["unreadable_files"], obj["planner"]["included_messages"],
                          obj["planner"]["partial"]), (0, 1, False))


# ---------------------------------------------------------------------------
# 规划端补测（kit-logs a002 复审：attempt-002 判 REVISE，预算用完，由规划端补齐）
# ---------------------------------------------------------------------------

class PlannerSupplementA002(OracleBase):
    """kit-logs a002 复审后规划端补的用例。

    - v2 合同 Steps 第 6 条让执行器删掉的 `test_bad_task_id_is_a_usage_error_for_every_subcommand` 并不完全与
      oracle 重复：它还覆盖 search、usage 的 `--task` 校验，oracle 原来只测了 list（B3、B6、B7.1）。
    - attempt 目录在两次列举之间变得列不出来：不得崩溃，按 B11(a) 跳过（规划端复审发现的窗口）。
    - search 跳过列不出来的 attempt；usage 不列 attempt 目录，照常读它的 events-summary.json（B11(a)）。
    - 目标的 `resolve()` 抛异常按找不到，退出码 2（B5.5、B5.6）。
    """

    unlistable = ReworkV2.unlistable
    run_checked = ReworkV2.run_checked
    json_checked = ReworkV2.json_checked

    def test_bad_task_filter_is_a_usage_error_for_search_and_usage(self):
        self.attempt("task-a", 1, summary="a\n")
        for argv in (["search", "a", "--task", "../x"], ["search", "a", "--task", "Task-A"],
                     ["usage", "--task", "../x"], ["usage", "--task", "Task-A"], ["usage", "--task", ""]):
            with self.subTest(argv=argv):
                self.assertUsageError(argv, error_line=False)

    def test_attempt_directory_that_stops_being_listable_is_skipped_without_a_crash(self):
        # 只断言不崩溃、其它 attempt 照常列出：只列一次的实现会把 attempt-002 正常列出，两次列举的实现必须跳过它。
        self.attempt("task-a", 1, summary="A1\n")
        self.attempt("task-a", 2, summary="A2\n")
        flaky_dir = os.path.normcase(os.path.abspath(str(self.runs / "task-a" / "attempt-002")))
        calls = {"n": 0}
        real_scandir = os.scandir

        def scandir(path=".", *args, **kwargs):
            if os.path.normcase(os.path.abspath(str(path))) == flaky_dir:
                calls["n"] += 1
                if calls["n"] > 1:
                    raise PermissionError(13, "第二次列目录被拒绝（替身）", str(path))
            return real_scandir(path, *args, **kwargs)

        with mock.patch.object(os, "scandir", scandir):
            code, obj, err = self.json_checked(["list"])
        self.assertEqual(code, 0, err)
        rows = [(row["task"], row["attempt"]) for row in obj["attempts"]]
        self.assertIn(("task-a", "attempt-001"), rows)

    def test_search_skips_an_unlistable_attempt_directory(self):
        self.attempt("task-a", 1, files={"notes.txt": "needle one\n"})
        self.attempt("task-a", 2, files={"notes.txt": "needle two\n"})
        with self.unlistable(self.runs / "task-a" / "attempt-002"):
            code, out, err = self.run_checked(["search", "needle"])
        self.assertEqual(code, 0, err)
        self.assertEqual([path for path, _line, _content in match_lines(out)], ["task-a/attempt-001/notes.txt"])

    def test_usage_reads_events_summary_of_an_unlistable_attempt_directory(self):
        events = {"usage": {"input": 1, "output": 2, "cacheRead": 3, "cacheWrite": 4, "totalTokens": 10},
                  "requested_model": MODEL_OBJ, "complete": True, "truncated": False, "parse_error_lines": []}
        self.attempt("task-a", 1, events=events)
        with self.unlistable(self.runs / "task-a" / "attempt-001"):
            code, obj, err = self.json_checked(["usage"])
        self.assertEqual(code, 0, err)
        self.assertEqual(obj["executor"]["counts"]["known"], 1)
        self.assertEqual(obj["executor"]["attempts"][0]["usage"]["totalTokens"], 10)

    def test_target_that_cannot_be_resolved_is_a_usage_error(self):
        self.attempt("task-a", 1, summary="a\n")
        real_resolve = Path.resolve

        def resolve(path_self, *args, **kwargs):
            if path_self.name == "attempt-001":
                raise RuntimeError("解析失败（替身）")
            return real_resolve(path_self, *args, **kwargs)

        with mock.patch.object(Path, "resolve", resolve):
            self.assertUsageError(["show", "task-a/attempt-001"])


# ---------------------------------------------------------------------------
# 闸二第 1 轮（Codex）的回归用例
# ---------------------------------------------------------------------------

class Gate2Round1(OracleBase):
    """S3：规划端统计为“部分”时，文本输出也要写明（设计 D4），不只是 JSON 的 partial。"""

    def test_partial_planner_stats_are_named_in_text_output(self):
        incomplete = self.root / "incomplete.jsonl"
        transcript(incomplete, [rec("p1", stop=None)])  # 只有中间记录：未完成，标“部分”
        code, out, err = run_logs(["usage", "--transcript", str(incomplete)], self.repo)
        self.assertEqual(code, 0, err)
        self.assertIn("部分", out)
        complete = self.root / "complete.jsonl"
        transcript(complete, [rec("c1")])
        code, out, err = run_logs(["usage", "--transcript", str(complete)], self.repo)
        self.assertEqual(code, 0, err)
        self.assertNotIn("部分", out)


if __name__ == "__main__":
    unittest.main()
