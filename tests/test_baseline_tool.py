#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""01-T1 基线取证工具 scripts/codekit/baseline.py 的离线自测（unittest）。

直接运行：python tests/test_baseline_tool.py
只在 tempfile 创建的临时目录中建立临时 Git 仓库；每个用例结束时只删除本测试自己创建的目录
（核对父目录是系统临时目录、目录名带本测试前缀，01 文档 8.4）。不调用 pi，不联网。
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True  # 导入被测模块时不在仓库中写 __pycache__

# 用例名、子测试参数与失败信息含中文和 U+212A 等字符；Windows 控制台默认代码页（如 cp1252）写不出时
# 会让报告本身抛 UnicodeEncodeError。统一改为 UTF-8，仍写不出的字符以 \\x.. 转义保留。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="backslashreplace")  # type: ignore[union-attr]
    except (AttributeError, ValueError):  # 被替换成不支持 reconfigure 的对象（如 StringIO 或 None）时保持原样
        pass

import contextlib  # noqa: E402
import hashlib  # noqa: E402
import importlib.util  # noqa: E402
import io  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
import stat  # noqa: E402
import subprocess  # noqa: E402
import tempfile  # noqa: E402
import time  # noqa: E402
import unittest  # noqa: E402
from pathlib import Path  # noqa: E402
from unittest import mock  # noqa: E402
from typing import Any, Dict, List, Optional, Tuple  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "scripts" / "codekit" / "baseline.py"
TEMP_PREFIX = "codekit-bl-test-"
GIT_REDIRECT = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
                "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_COMMON_DIR", "GIT_NAMESPACE", "GIT_PREFIX")


def _load_tool() -> Any:
    spec = importlib.util.spec_from_file_location("_codekit_baseline_under_test", str(TOOL))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


baseline = _load_tool()


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def base_env(**extra: str) -> Dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k.upper() not in GIT_REDIRECT}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["GIT_TERMINAL_PROMPT"] = "0"
    env.update(extra)
    return env


def _force_remove(func: Any, path: str, _info: Any) -> None:
    os.chmod(path, stat.S_IWRITE)  # Git 对象文件在 Windows 上是只读的
    func(path)


class TempArea:
    """本测试创建的临时目录；清理前核对归属，不在不确定时递归删除。"""

    def __init__(self) -> None:
        self.base = os.path.realpath(tempfile.gettempdir())
        self.path = Path(tempfile.mkdtemp(prefix=TEMP_PREFIX))

    def cleanup(self) -> None:
        real = os.path.realpath(str(self.path))
        if os.path.normcase(os.path.dirname(real)) != os.path.normcase(self.base) \
                or not os.path.basename(real).startswith(TEMP_PREFIX):
            raise AssertionError("拒绝清理归属不明的目录：%s" % real)
        if sys.version_info >= (3, 12):
            shutil.rmtree(real, onexc=_force_remove)
        else:
            shutil.rmtree(real, onerror=_force_remove)


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git"] + list(args), cwd=str(repo), env=base_env(), stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)


def make_repo(area: TempArea, files: Dict[str, bytes], name: str = "repo") -> Path:
    repo = area.path / name
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "core.autocrlf", "false")
    git(repo, "config", "user.name", "baseline-test")
    git(repo, "config", "user.email", "baseline-test@example.invalid")
    for rel, data in files.items():
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "init")
    return repo


def run_tool(args: List[str], cwd: Path, env: Optional[Dict[str, str]] = None,
             timeout: float = 240) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(TOOL)] + args, cwd=str(cwd), env=env or base_env(),
                          stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)


def py_cmd(code: str) -> List[str]:
    return [sys.executable, "-c", code]


def short_path(path: str) -> Optional[str]:
    """Windows 8.3 短名（测试自己调用 GetShortPathNameW，不经被测模块）；不可得时返回 None。"""
    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    func = k32.GetShortPathNameW
    func.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
    func.restype = wintypes.DWORD
    buf = ctypes.create_unicode_buffer(1024)
    got = func(path, buf, 1024)
    return buf.value if 0 < got < 1024 else None


def pid_alive(pid: int) -> bool:
    if os.name == "nt":
        import ctypes

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.OpenProcess.restype = ctypes.c_void_p
        handle = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            if not k32.GetExitCodeProcess(ctypes.c_void_p(handle), ctypes.byref(code)):
                return False
            return code.value == 259  # STILL_ACTIVE
        finally:
            k32.CloseHandle(ctypes.c_void_p(handle))
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class _AreaCase(unittest.TestCase):
    def setUp(self) -> None:
        self.area = TempArea()
        self.addCleanup(self.area.cleanup)
        self.out_root = self.area.path / "out"

    def capture(self, repo: Path, capture_id: str, command: List[str], extra: Optional[List[str]] = None,
                env: Optional[Dict[str, str]] = None) -> Tuple[subprocess.CompletedProcess, Optional[Dict[str, Any]]]:
        args = ["capture", "--out-root", str(self.out_root), "--capture-id", capture_id] + (extra or []) + \
               ["--"] + command
        proc = run_tool(args, repo, env=env)
        record_path = self.out_root / capture_id / "capture.json"
        record = json.loads(record_path.read_bytes().decode("utf-8")) if record_path.is_file() else None
        return proc, record

    def assert_refs_match(self, capture_dir: Path, record: Dict[str, Any]) -> None:
        self.assertTrue(record["files"])
        for ref in record["files"]:
            path = capture_dir / ref["path"]
            self.assertTrue(path.is_file(), ref["path"])
            self.assertEqual(sha256_of(path), ref["sha256"], ref["path"])
            self.assertEqual(path.stat().st_size, ref["bytes"], ref["path"])

    def manifest(self, record: Dict[str, Any], phase: str, capture_id: str) -> Dict[str, Any]:
        path = self.out_root / capture_id / record[phase]["input_manifest"]["path"]
        return json.loads(path.read_bytes().decode("utf-8"))

    def assert_manifest_drift_explained(self, record: Dict[str, Any]) -> None:
        """每条输入清单漂移都必须带有可解释的差异项（逐文件、忽略项名称或其他字段）。"""
        for entry in record["comparison"]["drift"]:
            if entry["check"] == "input_manifest_sha256":
                self.assertTrue(entry["explained"], entry)
                self.assertTrue(entry["changes"] or entry["ignored_names_added"] or entry["ignored_names_removed"]
                                or entry["other_fields"], entry)


# ---------------------------------------------------------------------------
# 纯函数
# ---------------------------------------------------------------------------

class PorcelainParserTests(unittest.TestCase):
    def test_rename_copy_space_and_chinese_paths(self) -> None:
        data = (" M a b.txt\0R  新 名.txt\0old name.txt\0?? 中文 目录/文 件.txt\0C  c2.txt\0c1.txt\0"
                " R wt-new\0wt-old\0").encode("utf-8")
        entries = baseline.parse_porcelain_v1_z(data)
        self.assertEqual([(e["xy"], e["path"], e["orig_path"]) for e in entries], [
            (" M", "a b.txt", None),
            ("R ", "新 名.txt", "old name.txt"),
            ("??", "中文 目录/文 件.txt", None),
            ("C ", "c2.txt", "c1.txt"),
            (" R", "wt-new", "wt-old"),
        ])
        self.assertTrue(all(e["path_utf8"] for e in entries))

    def test_newline_in_path_is_not_split(self) -> None:
        entries = baseline.parse_porcelain_v1_z(b"?? a\nb.txt\0 M c\0")
        self.assertEqual([e["path"] for e in entries], ["a\nb.txt", "c"])

    def test_empty_output(self) -> None:
        self.assertEqual(baseline.parse_porcelain_v1_z(b""), [])

    def test_malformed_records_are_rejected(self) -> None:
        for bad in (b"R  new\0", b"R  new\0\0", b" M no-terminator", b"XY path\0", b" Mpath\0", b" M \0", b"??"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    baseline.parse_porcelain_v1_z(bad)

    def test_non_utf8_path_is_flagged(self) -> None:
        entries = baseline.parse_porcelain_v1_z(b"?? \xff\xfe.bin\0")
        self.assertFalse(entries[0]["path_utf8"])

    def test_real_git_output_with_rename(self) -> None:
        area = TempArea()
        self.addCleanup(area.cleanup)
        repo = make_repo(area, {"old name.txt": b"old\n"})
        git(repo, "mv", "old name.txt", "新 名.txt")
        (repo / "中文 目录").mkdir()
        (repo / "中文 目录" / "文 件.txt").write_bytes(b"x")
        out = git(repo, "-c", "core.fsmonitor=false", "status", "--porcelain=v1", "-z", "--untracked-files=all").stdout
        entries = baseline.parse_porcelain_v1_z(out)
        self.assertIn(("R ", "新 名.txt", "old name.txt"), [(e["xy"], e["path"], e["orig_path"]) for e in entries])
        self.assertIn(("??", "中文 目录/文 件.txt", None), [(e["xy"], e["path"], e["orig_path"]) for e in entries])


class RuleTests(unittest.TestCase):
    def test_exclusion_is_exact_prefix(self) -> None:
        self.assertEqual(baseline.match_exclusion("out/a.txt", ["out/"]), "out/")
        self.assertIsNone(baseline.match_exclusion("outx/a.txt", ["out/"]))
        self.assertIsNone(baseline.match_exclusion("out", ["out/"]))
        self.assertEqual(baseline.match_exclusion("out", ["out"]), "out")
        self.assertIsNone(baseline.match_exclusion("out/a.txt", ["out"]))
        self.assertIsNone(baseline.match_exclusion("Out/a.txt", ["out/"]))

    def test_invalid_excludes(self) -> None:
        for bad in ("", "/abs/", "C:/x/", "a\\b/", "../x/", "a/../b/", "./a/", "a//b/", "a/\n/"):
            with self.subTest(bad=bad):
                self.assertIsNotNone(baseline.validate_exclude(bad))
        for good in ("out/", ".agent/baseline/", "文档/说明.md"):
            with self.subTest(good=good):
                self.assertIsNone(baseline.validate_exclude(good))

    def test_capture_id_rules(self) -> None:
        self.assertIsNone(baseline.validate_capture_id("bl-20260925T000000Z-0123abcd"))
        for bad in ("../x", "a/b", "", ".hidden", "NUL", "com1.txt", "x.", "a b"):
            with self.subTest(bad=bad):
                self.assertIsNotNone(baseline.validate_capture_id(bad))
        self.assertRegex(baseline.default_capture_id(), r"^bl-\d{8}T\d{6}Z-[0-9a-f]{8}$")

    def test_canonical_json(self) -> None:
        self.assertEqual(baseline.canonical_json_bytes({"b": 1, "a": "中"}), '{"a":"中","b":1}\n'.encode("utf-8"))
        with self.assertRaises(ValueError):
            baseline.canonical_json_bytes({"x": float("nan")})


class RunReasonTests(unittest.TestCase):
    def record(self, **fields: Any) -> Dict[str, Any]:
        run = baseline.new_run_record(["x"], 10.0, 1.0)
        run.update(fields)
        return run

    def test_command_that_did_not_run_is_always_incomplete(self) -> None:
        ref = {"path": "run/stdout.bin", "sha256": "0" * 64, "bytes": 0}
        cases = [
            (dict(reason="output_write_failed"), "run_output_write_failed"),
            (dict(attempted=True, reason="spawn_failed", stdout=ref, stderr=ref), "run_spawn_failed"),
            (dict(attempted=True, executed=None, reason="supervisor_error", stdout=ref, stderr=ref),
             "run_supervisor_error"),
            (dict(attempted=True, executed=True, reason="interrupted", stdout=ref, stderr=ref), "run_interrupted"),
            (dict(attempted=True, executed=True, reason="timeout", termination_confirmed=False, stdout=ref,
                  stderr=ref), "run_termination_unconfirmed"),
            (dict(attempted=True, executed=True, returncode=0, output_close_error="OSError: x", stdout=ref,
                  stderr=ref), "run_output_close_failed"),
            (dict(attempted=True, executed=True, returncode=0, stdout=ref), "run_output_missing"),
            (dict(), "run_not_executed"),
        ]
        for fields, expected in cases:
            with self.subTest(fields=fields):
                self.assertIn(expected, baseline.run_incomplete_reasons(self.record(**fields)))

    def test_completed_command_is_complete_whatever_its_exit_code(self) -> None:
        ref = {"path": "run/stdout.bin", "sha256": "0" * 64, "bytes": 0}
        for code in (0, 1, 3):
            with self.subTest(code=code):
                run = self.record(attempted=True, executed=True, returncode=code, stdout=ref, stderr=ref)
                self.assertEqual(baseline.run_incomplete_reasons(run), [])
        run = self.record(attempted=True, executed=True, reason="timeout", termination_confirmed=True,
                          stdout=ref, stderr=ref)
        self.assertEqual(baseline.run_incomplete_reasons(run), [])


class ImportSideEffectTests(unittest.TestCase):
    def test_import_runs_no_command_and_writes_nothing(self) -> None:
        area = TempArea()
        self.addCleanup(area.cleanup)
        codekit_dir = TOOL.parent
        before = sorted(os.listdir(str(codekit_dir)))
        code = (
            "import sys, subprocess, os, importlib.util\n"
            "sys.dont_write_bytecode = True\n"
            "def boom(*a, **k): raise AssertionError('import started a process')\n"
            "subprocess.Popen = boom; os.system = boom\n"
            "spec = importlib.util.spec_from_file_location('bl', sys.argv[1])\n"
            "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n"
            "assert '_codekit_pi_dispatch' not in sys.modules\n"
            "print('OK')\n"
        )
        proc = subprocess.run([sys.executable, "-c", code, str(TOOL)], cwd=str(area.path), env=base_env(),
                              stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        self.assertEqual(proc.stdout.strip(), b"OK")
        self.assertEqual(os.listdir(str(area.path)), [])
        self.assertEqual(sorted(os.listdir(str(codekit_dir))), before)


# ---------------------------------------------------------------------------
# capture
# ---------------------------------------------------------------------------

class CaptureTests(_AreaCase):
    def test_unchanged_command_is_consistent(self) -> None:
        repo = make_repo(self.area, {"a.txt": b"a\n", "dir with space/b.txt": b"b\n"})
        proc, record = self.capture(repo, "ok1", py_cmd("print(1)"))
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        self.assertIn(str(self.out_root / "ok1"), proc.stdout.decode("utf-8"))
        assert record is not None
        self.assertEqual(record["schema_version"], 1)
        self.assertEqual(record["record_type"], "baseline-capture")
        self.assertEqual(record["execution_status"], "complete")
        self.assertIs(record["comparison"]["baseline_consistent"], True)
        self.assertEqual(record["comparison"]["drift"], [])
        self.assertEqual(record["run"]["returncode"], 0)
        self.assertEqual(record["run"]["interpretation"], "not_evaluated")
        self.assertEqual((self.out_root / "ok1" / "run" / "stdout.bin").read_bytes().strip(), b"1")
        self.assertEqual(record["tool"]["sha256"], sha256_of(TOOL))
        self.assertEqual(record["pre"]["facts"]["head_object_type"], "commit")
        self.assertRegex(record["pre"]["facts"]["head"], r"^[0-9a-f]{40}([0-9a-f]{24})?$")
        self.assert_refs_match(self.out_root / "ok1", record)
        manifest = self.manifest(record, "pre", "ok1")
        paths = {i["path"]: i for i in manifest["items"]}
        self.assertEqual(paths["a.txt"]["sha256"], hashlib.sha256(b"a\n").hexdigest())
        self.assertIn("dir with space/b.txt", paths)
        self.assertEqual(manifest["exclusions"]["rules"][0]["entry"], ".agent/baseline/")
        self.assertEqual(manifest["ignored"]["closure"], "not_included")
        raw = (self.out_root / "ok1" / record["pre"]["input_manifest"]["path"]).read_bytes()
        self.assertEqual(raw, baseline.canonical_json_bytes(manifest))
        self.assertNotIn("capture_sha256", record)

    def test_modifying_tracked_file_is_drift(self) -> None:
        repo = make_repo(self.area, {"a.txt": b"a\n", "keep.txt": b"k\n"})
        proc, record = self.capture(repo, "mod1", py_cmd("open('a.txt','ab').write(b'changed')"))
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        assert record is not None
        self.assertEqual(record["execution_status"], "complete")
        self.assertIs(record["comparison"]["baseline_consistent"], False)
        drift = {d["check"]: d for d in record["comparison"]["drift"]}
        self.assertIn("porcelain_raw_bytes", drift)
        self.assertIn("diff_unstaged_bytes", drift)
        self.assertEqual(drift["porcelain_raw_bytes"]["paths"], ["a.txt"])
        self.assertEqual(drift["input_manifest_sha256"]["paths"], ["a.txt"])
        self.assertIs(drift["input_manifest_sha256"]["closure_sha256_equal"], False)
        change = drift["input_manifest_sha256"]["changes"][0]
        self.assertEqual(change["change"], "modified")
        self.assertIn("sha256", change["fields"])
        self.assert_manifest_drift_explained(record)

    def test_new_untracked_file_is_drift(self) -> None:
        repo = make_repo(self.area, {"a.txt": b"a\n"})
        proc, record = self.capture(repo, "new1", py_cmd("open('新 文件.txt','wb').write(b'n')"))
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        assert record is not None
        self.assertIs(record["comparison"]["baseline_consistent"], False)
        drift = {d["check"]: d for d in record["comparison"]["drift"]}
        self.assertEqual(drift["porcelain_raw_bytes"]["paths"], ["新 文件.txt"])
        changes = drift["input_manifest_sha256"]["changes"]
        self.assertEqual([(c["path"], c["change"]) for c in changes], [("新 文件.txt", "added")])
        self.assertEqual(changes[0]["post"]["source"], "untracked")
        self.assertNotIn("diff_unstaged_bytes", drift)  # 未跟踪文件不出现在 diff 中，由清单发现
        self.assert_manifest_drift_explained(record)

    def test_exclude_is_exact_prefix_and_does_not_hide_porcelain_changes(self) -> None:
        repo = make_repo(self.area, {"out/a.txt": b"a\n", "outx/b.txt": b"b\n"})
        proc, record = self.capture(repo, "ex1", py_cmd("open('out/a.txt','ab').write(b'!')"),
                                    extra=["--exclude", "out/"])
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        assert record is not None
        manifest = self.manifest(record, "pre", "ex1")
        paths = [i["path"] for i in manifest["items"]]
        self.assertIn("outx/b.txt", paths)
        self.assertNotIn("out/a.txt", paths)
        self.assertEqual(manifest["exclusions"]["rules"], [{"entry": "out/", "match": "prefix"}])
        self.assertEqual(record["pre"]["exclusion_counts"], {"out/": {"ignored_names": 0, "inputs": 1}})
        drift = {d["check"]: d for d in record["comparison"]["drift"]}
        self.assertNotIn("input_manifest_sha256", drift)  # 被排除的路径不在清单中
        self.assertEqual(drift["porcelain_raw_bytes"]["paths"], ["out/a.txt"])  # 但变化仍被发现
        self.assertIs(record["comparison"]["baseline_consistent"], False)

    def test_new_file_under_excluded_prefix_causes_no_unexplained_manifest_drift(self) -> None:
        # 回归：排除计数曾写入清单并进入 closure 摘要，产生 paths/changes 都为空、无法解释的清单漂移。
        repo = make_repo(self.area, {"out/a.txt": b"a\n", "outx/b.txt": b"b\n"})
        proc, record = self.capture(repo, "ex2", py_cmd("open('out/new.txt','wb').write(b'n')"),
                                    extra=["--exclude", "out/"])
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        assert record is not None
        drift = {d["check"]: d for d in record["comparison"]["drift"]}
        self.assertNotIn("input_manifest_sha256", drift)
        self.assertEqual(record["pre"]["input_manifest"]["sha256"], record["post"]["input_manifest"]["sha256"])
        self.assertEqual(drift["porcelain_raw_bytes"]["paths"], ["out/new.txt"])
        observations = {o["observation"]: o for o in record["comparison"]["observations"]}
        excluded = observations["excluded_path_counts_changed"]
        self.assertTrue(excluded["not_counted_as_drift"])
        self.assertEqual(excluded["pre"]["out/"]["inputs"], 1)
        self.assertEqual(excluded["post"]["out/"]["inputs"], 2)
        self.assertIs(record["comparison"]["baseline_consistent"], False)
        self.assert_manifest_drift_explained(record)

    def test_ignored_name_change_is_drift(self) -> None:
        # 回归：忽略项名称的增减曾只记为观察，baseline_consistent 仍为 true；规格要求比较输入清单 sha256。
        repo = make_repo(self.area, {".gitignore": b"*.log\n", "a.txt": b"a\n"})
        proc, record = self.capture(repo, "ig1", py_cmd("open('x.log','wb').write(b'l')"))
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        assert record is not None
        self.assertEqual(record["execution_status"], "complete")
        self.assertIs(record["comparison"]["baseline_consistent"], False)
        drift = {d["check"]: d for d in record["comparison"]["drift"]}
        self.assertNotIn("porcelain_raw_bytes", drift)  # 忽略文件不出现在 porcelain 中
        entry = drift["input_manifest_sha256"]
        self.assertEqual(entry["ignored_names_added"], ["x.log"])
        self.assertEqual(entry["ignored_names_removed"], [])
        self.assertEqual(entry["changes"], [])
        self.assertIs(entry["closure_sha256_equal"], True)
        self.assertIs(record["comparison"]["input_manifest_closure_sha256_equal"], True)
        self.assertEqual(self.manifest(record, "post", "ig1")["ignored"]["names"], ["x.log"])
        self.assert_manifest_drift_explained(record)

    def test_ignored_names_respect_exclude(self) -> None:
        repo = make_repo(self.area, {".gitignore": b"*.log\n", "a.txt": b"a\n"})
        code = "import os; os.mkdir('logs'); open('logs/a.log','wb').write(b'l')"
        proc, record = self.capture(repo, "ig2", py_cmd(code), extra=["--exclude", "logs/"])
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        assert record is not None
        self.assertIs(record["comparison"]["baseline_consistent"], True, record["comparison"]["drift"])
        self.assertEqual(self.manifest(record, "post", "ig2")["ignored"]["names"], [])
        self.assertEqual(record["post"]["exclusion_counts"], {"logs/": {"ignored_names": 1, "inputs": 0}})

    def test_existing_capture_dir_is_not_overwritten(self) -> None:
        repo = make_repo(self.area, {"a.txt": b"a\n"})
        existing = self.out_root / "fixed"
        existing.mkdir(parents=True)
        (existing / "sentinel.txt").write_bytes(b"keep")
        proc = run_tool(["capture", "--out-root", str(self.out_root), "--capture-id", "fixed", "--"] +
                        py_cmd("print(1)"), repo)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(os.listdir(str(existing)), ["sentinel.txt"])
        self.assertEqual((existing / "sentinel.txt").read_bytes(), b"keep")

    def test_missing_executable_is_null_returncode_and_incomplete(self) -> None:
        repo = make_repo(self.area, {"a.txt": b"a\n"})
        proc, record = self.capture(repo, "nx1", ["codekit-no-such-executable-4f1c"])
        self.assertEqual(proc.returncode, 1)
        assert record is not None
        self.assertIsNone(record["run"]["returncode"])
        self.assertEqual(record["run"]["reason"], "spawn_failed")
        self.assertTrue(record["run"]["spawn_error"])
        self.assertIs(record["run"]["attempted"], True)
        self.assertIs(record["run"]["executed"], False)  # 回归：启动失败曾被记为 executed=true
        self.assertIs(record["comparison"]["command_executed"], False)
        self.assertEqual(record["execution_status"], "incomplete")
        self.assertIn("run_spawn_failed", record["incomplete_reasons"])

    def test_run_output_write_failure_is_incomplete_and_command_not_run(self) -> None:
        # 回归：run/ 写不出来时曾记为 execution_status=complete、退出码 0。这里在进程内让 run/ 预先存在，
        # 使 run_dir.mkdir() 抛出 FileExistsError（OSError），并确认被测命令没有运行。
        repo = make_repo(self.area, {"a.txt": b"a\n"})
        marker = self.area.path / "marker-should-not-exist.txt"
        original = baseline.run_command

        def failing_run_command(ctx: Any, *args: Any, **kwargs: Any) -> Any:
            (ctx.capture_dir / "run").mkdir()
            return original(ctx, *args, **kwargs)

        baseline.run_command = failing_run_command
        self.addCleanup(setattr, baseline, "run_command", original)
        previous_cwd = os.getcwd()
        os.chdir(str(repo))
        self.addCleanup(os.chdir, previous_cwd)  # 先于临时目录清理执行（addCleanup 后进先出）
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = baseline.main(["capture", "--out-root", str(self.out_root), "--capture-id", "wf1", "--",
                                  sys.executable, "-c", "open(%r, 'wb').write(b'x')" % str(marker)])
        self.assertEqual(code, 1, err.getvalue())
        record = json.loads((self.out_root / "wf1" / "capture.json").read_bytes().decode("utf-8"))
        self.assertEqual(record["execution_status"], "incomplete")
        self.assertIn("run_output_write_failed", record["incomplete_reasons"])
        run = record["run"]
        self.assertEqual(run["reason"], "output_write_failed")
        self.assertIsNone(run["returncode"])
        self.assertIs(run["attempted"], False)
        self.assertIs(run["executed"], False)
        self.assertTrue(run["error"])
        self.assertIs(record["comparison"]["command_executed"], False)
        self.assertFalse(marker.exists())
        self.assertIn("execution_status: incomplete", out.getvalue())
        self.assert_refs_match(self.out_root / "wf1", record)

    def test_timeout_is_recorded_and_process_tree_ended(self) -> None:
        repo = make_repo(self.area, {"a.txt": b"a\n"})
        code = ("import os, subprocess, sys, time\n"
                "c = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])\n"
                "print(os.getpid(), c.pid, flush=True)\n"
                "time.sleep(120)\n")
        started = time.monotonic()
        proc, record = self.capture(repo, "to1", py_cmd(code), extra=["--timeout", "2", "--grace", "1"])
        elapsed = time.monotonic() - started
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        self.assertLess(elapsed, 90)
        assert record is not None
        run = record["run"]
        self.assertTrue(run["timed_out"])
        self.assertIsNone(run["returncode"])
        self.assertEqual(run["reason"], "timeout")
        self.assertTrue(run["termination_confirmed"])
        self.assertEqual(record["execution_status"], "complete")
        pids = [int(x) for x in (self.out_root / "to1" / "run" / "stdout.bin").read_bytes().split()]
        self.assertEqual(len(pids), 2)
        deadline = time.monotonic() + 20
        while any(pid_alive(p) for p in pids) and time.monotonic() < deadline:
            time.sleep(0.2)
        self.assertEqual([p for p in pids if pid_alive(p)], [])

    @unittest.skipUnless(os.name == "nt", "Job Object 强制结束路径只在 Windows 上存在")
    def test_timeout_forces_job_termination_when_ctrl_break_is_ignored(self) -> None:
        # 回归：上一个用例的进程会在宽限期内被 CTRL_BREAK 结束，走不到 Job Object 强制结束这条路径。
        # 这里子进程与孙进程都忽略 SIGBREAK，孙进程还脱离控制台（DETACHED_PROCESS）并自成进程组。
        repo = make_repo(self.area, {"a.txt": b"a\n"})
        grandchild = "import signal, time; signal.signal(signal.SIGBREAK, signal.SIG_IGN); time.sleep(120)"
        code = ("import os, signal, subprocess, sys, time\n"
                "signal.signal(signal.SIGBREAK, signal.SIG_IGN)\n"
                "flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS\n"
                "c = subprocess.Popen([sys.executable, '-c', %r], creationflags=flags,\n"
                "                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
                "print(os.getpid(), c.pid, flush=True)\n"
                "time.sleep(120)\n") % grandchild
        started = time.monotonic()
        proc, record = self.capture(repo, "to2", py_cmd(code), extra=["--timeout", "3", "--grace", "1"])
        elapsed = time.monotonic() - started
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        self.assertLess(elapsed, 90)
        assert record is not None
        run = record["run"]
        self.assertTrue(run["timed_out"])
        self.assertIsNone(run["returncode"])
        self.assertEqual(run["reason"], "timeout")
        self.assertTrue(run["termination_confirmed"])
        self.assertEqual(run["kill_method"], "job-object")
        status = run["exit_status_after_termination"]
        self.assertIsNotNone(status)
        self.assertNotEqual(status, 0xC000013A)  # STATUS_CONTROL_C_EXIT：说明是 CTRL_BREAK 结束的，不是强制结束
        self.assertEqual(record["execution_status"], "complete")
        pids = [int(x) for x in (self.out_root / "to2" / "run" / "stdout.bin").read_bytes().split()]
        self.assertEqual(len(pids), 2)
        deadline = time.monotonic() + 20
        while any(pid_alive(p) for p in pids) and time.monotonic() < deadline:
            time.sleep(0.2)
        self.assertEqual([p for p in pids if pid_alive(p)], [])

    def test_environment_values_are_not_recorded(self) -> None:
        repo = make_repo(self.area, {"a.txt": b"a\n"})
        marker = "codekit-env-marker-9b41e7"
        env = base_env(STUB_SCENARIO=marker, PI_EXEC_MODEL=marker + "-model")
        proc, record = self.capture(repo, "env1", py_cmd("print(1)"), env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        assert record is not None
        env_path = self.out_root / "env1" / record["pre"]["environment"]["path"]
        facts = json.loads(env_path.read_bytes().decode("utf-8"))
        self.assertIs(facts["env_names_present"]["STUB_SCENARIO"], True)
        self.assertIs(facts["env_names_present"]["PI_EXEC_MODEL"], True)
        for dirpath, _dirs, files in os.walk(str(self.out_root / "env1")):
            for name in files:
                data = Path(dirpath, name).read_bytes()
                self.assertNotIn(marker.encode(), data, os.path.join(dirpath, name))

    def test_output_inside_repo_must_be_git_ignored(self) -> None:
        repo = make_repo(self.area, {"a.txt": b"a\n"})
        proc = run_tool(["capture", "--out-root", "evidence", "--capture-id", "in1", "--"] + py_cmd("print(1)"), repo)
        self.assertEqual(proc.returncode, 2)
        self.assertFalse((repo / "evidence").exists())
        (repo / ".gitignore").write_bytes(b"evidence/\n")
        git(repo, "add", ".gitignore")
        git(repo, "commit", "-q", "-m", "ignore evidence")
        proc = run_tool(["capture", "--out-root", "evidence", "--capture-id", "in2", "--"] + py_cmd("print(1)"), repo)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        record = json.loads((repo / "evidence" / "in2" / "capture.json").read_bytes().decode("utf-8"))
        self.assertTrue(record["output_location"]["inside_repo"])
        self.assertTrue(record["output_location"]["git_ignored"])
        self.assertEqual(record["output_location"]["repo_relative"], "evidence/in2")
        self.assertIs(record["comparison"]["baseline_consistent"], True)

    def test_usage_errors(self) -> None:
        repo = make_repo(self.area, {"a.txt": b"a\n"})
        out = str(self.out_root)
        cases = [
            ["capture", "--out-root", out, "python", "-c", "1"],
            ["capture", "--out-root", out, "--"],
            ["capture", "--out-root", out, "--capture-id", "../x", "--", "python"],
            ["capture", "--out-root", out, "--timeout", "0", "--", "python"],
            ["capture", "--out-root", out, "--exclude", "../x/", "--", "python"],
            ["capture", "--", "python"],
            ["frobnicate"],
            [],
        ]
        for args in cases:
            with self.subTest(args=args):
                self.assertEqual(run_tool(args, repo).returncode, 2)
        self.assertFalse(self.out_root.exists())


# ---------------------------------------------------------------------------
# 路径包含判定（is_within / relative_within）及其调用点
# ---------------------------------------------------------------------------

KELVIN = "K"  # KELVIN SIGN：str.lower() 后是 ASCII k，在 NTFS 上与 k 是两个名称


def _ascii_swapcase(text: str) -> str:
    """只交换 ASCII 字母的大小写（大小写不敏感目录中同一对象的另一种写法），其他字符原样保留。"""
    return "".join(c.swapcase() if c.isascii() and c.isalpha() else c for c in text)


def _str_lower_normcase(s: Any) -> str:
    """模拟没有 LCMapStringEx 的 ntpath.normcase（退化为 str.lower()），它会把 U+212A 折叠成 k。"""
    return os.fspath(s).replace("/", os.sep).lower()


class PathContainmentTests(_AreaCase):
    def make_kelvin_sibling(self, work: Path) -> Path:
        """在 work 旁边建立名称只差 k/U+212A 的兄弟目录。"""
        sibling = work.parent / (work.name[:-1] + KELVIN)
        self.assertEqual(work.name[-1], "k")
        try:
            sibling.mkdir()
        except FileExistsError:
            self.skipTest("本文件系统把 U+212A 与 k 视为同一名称，无法构造兄弟目录")
        self.assertIn(sibling.name, os.listdir(str(work.parent)))
        return sibling

    def test_kelvin_sign_sibling_is_outside(self) -> None:
        # 回归：按折叠大小写后的字符串比较，会把名称只差 k/U+212A 的根外兄弟目录判为根内。
        work = self.area.path / "work"
        (work / "sub").mkdir(parents=True)
        kelvin = self.make_kelvin_sibling(work)
        (kelvin / "sub").mkdir()
        self.assertTrue(baseline.is_within(str(work), str(work)))
        self.assertEqual(baseline.relative_within(str(work), str(work)), ".")
        self.assertEqual(baseline.relative_within(str(work / "sub" / "not-yet"), str(work)), "sub/not-yet")
        outside = [kelvin, kelvin / "sub", kelvin / "sub" / "not-yet", work / ".." / kelvin.name / "sub"]
        for child in outside:
            with self.subTest(child=str(child)):
                self.assertFalse(baseline.is_within(str(child), str(work)))
                self.assertIsNone(baseline.relative_within(str(child), str(work)))
        self.assertFalse(baseline.is_within(str(work / "sub"), str(kelvin)))
        # normcase 退化为 str.lower() 的实现上，判定也不能随之把 U+212A 折叠成 k。
        with mock.patch.object(os.path, "normcase", _str_lower_normcase):
            for child in outside:
                with self.subTest(child=str(child), normcase="str.lower"):
                    self.assertFalse(baseline.is_within(str(child), str(work)))
            self.assertTrue(baseline.is_within(str(work / "sub"), str(work)))

    @unittest.skipUnless(os.name == "nt", "大小写不敏感查找与 8.3 短名只在 Windows 上存在")
    def test_other_spellings_of_same_directory_are_inside(self) -> None:
        # 逐字比较分段前先 realpath：同一目录的 ASCII 大小写变体、/ 分隔写法、长名与 8.3 短名都算在内，
        # 不能因为改成逐字比较就漏判（archive 目标检查依赖这一方向）。
        work = self.area.path / "work"
        long_dir = work / "long directory name"
        (long_dir / "sub").mkdir(parents=True)
        (work / "sub").mkdir()
        real_work = os.path.realpath(str(work))
        cases = [
            (_ascii_swapcase(str(work / "sub")), str(work), "sub"),
            (str(work / "sub"), _ascii_swapcase(str(work)), "sub"),
            (str(work).replace("\\", "/") + "/sub", str(work), "sub"),
            (os.path.join(real_work, "sub"), str(work), "sub"),
            (str(work / "sub"), real_work, "sub"),
        ]
        short = short_path(str(long_dir))
        if short and short.lower() != os.path.realpath(str(long_dir)).lower():
            cases.append((os.path.join(short, "sub"), str(work), "long directory name/sub"))
            cases.append((str(long_dir / "sub"), short, "sub"))
        for child, parent, rel in cases:
            with self.subTest(child=child, parent=parent):
                self.assertTrue(baseline.is_within(child, parent))
                self.assertEqual(baseline.relative_within(child, parent), rel)
        self.assertTrue(baseline.is_within(_ascii_swapcase(str(work / "sub" / "not-yet")), str(work)))

    @unittest.skipUnless(os.name == "nt", "按目录大小写敏感是 NTFS 特性")
    def test_case_sensitive_directory_sibling_is_outside(self) -> None:
        # 回归：开启按目录大小写敏感后 Repo 与 repo 是两个目录；normcase 后比较会把 repo 判为 Repo 之内。
        cs = self.area.path / "cs"
        cs.mkdir()
        fsutil = shutil.which("fsutil")
        if fsutil is None:
            self.skipTest("找不到 fsutil，无法开启按目录大小写敏感")
        proc = subprocess.run([fsutil, "file", "setCaseSensitiveInfo", str(cs), "enable"], stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        if proc.returncode != 0:
            self.skipTest("无法为测试目录开启按目录大小写敏感（fsutil 返回 %d）" % proc.returncode)
        upper, lower = cs / "Repo", cs / "repo"
        upper.mkdir()
        lower.mkdir()  # 若 fsutil 报告成功却未生效，这里抛 FileExistsError，用例失败而不是跳过
        self.assertFalse(baseline.is_within(str(lower), str(upper)))
        self.assertFalse(baseline.is_within(str(lower / "x"), str(upper)))
        self.assertFalse(baseline.is_within(str(upper / "x"), str(lower)))
        self.assertTrue(baseline.is_within(str(upper / "x"), str(upper)))
        self.assertEqual(baseline.relative_within(str(lower / "x"), str(lower)), "x")

    def test_capture_out_root_in_kelvin_sibling_of_repo_is_outside_repo(self) -> None:
        # --out-root 调用点：仓库根的 U+212A 兄弟目录在仓库外，不要求被 Git 忽略；toplevel 核对仍一致。
        repo = make_repo(self.area, {"a.txt": b"a\n"}, name="work")
        sibling = self.make_kelvin_sibling(repo)
        self.out_root = sibling / "evidence"
        proc, record = self.capture(repo, "ks1", py_cmd("print(1)"))
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        assert record is not None
        self.assertIs(record["output_location"]["inside_repo"], False)
        self.assertIsNone(record["output_location"]["repo_relative"])
        self.assertIsNone(record["output_location"]["git_ignored"])
        self.assertIs(record["pre"]["facts"]["toplevel_matches_repo_root"], True)
        self.assertIs(record["post"]["facts"]["toplevel_matches_repo_root"], True)
        self.assertIs(record["comparison"]["baseline_consistent"], True)

    @unittest.skipUnless(os.name == "nt", "大小写不敏感查找只在 Windows 上存在")
    def test_capture_out_root_under_other_spelling_of_repo_is_inside_repo(self) -> None:
        # --out-root / --exclude 调用点：以 ASCII 大小写变体写出的仓库内目录仍判为仓库内；
        # 未被忽略时拒绝并只删除本次新建的空目录，已忽略时 repo_relative 用磁盘上的真实拼写匹配 --exclude。
        repo = make_repo(self.area, {"a.txt": b"a\n", ".gitignore": b"evidence/\n"}, name="work")
        other = _ascii_swapcase(str(repo / "unignored"))
        proc = run_tool(["capture", "--out-root", other, "--capture-id", "ks2", "--"] + py_cmd("print(1)"), repo)
        self.assertEqual(proc.returncode, 2, proc.stderr.decode("utf-8", "replace"))
        self.assertNotIn("UNIGNORED", os.listdir(str(repo)))
        self.assertNotIn("unignored", os.listdir(str(repo)))
        (repo / "evidence").mkdir()
        self.out_root = Path(_ascii_swapcase(str(repo / "evidence")))
        proc, record = self.capture(repo, "ks3", py_cmd("print(1)"), extra=["--exclude", "evidence/"])
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        assert record is not None
        self.assertIs(record["output_location"]["inside_repo"], True)
        self.assertEqual(record["output_location"]["repo_relative"], "evidence/ks3")
        self.assertIs(record["output_location"]["git_ignored"], True)
        self.assertEqual(record["output_location"]["covered_by_exclude"], "evidence/")
        self.assertIs(record["comparison"]["baseline_consistent"], True)

    def test_archive_dest_inside_capture_dir_is_refused_under_any_spelling(self) -> None:
        # archive 目标调用点：--dest 以另一种写法指向取证目录内部时仍拒绝，且不创建任何目录；
        # 取证目录名称只差 k/U+212A 的兄弟目录在取证目录外，允许归档。
        repo = make_repo(self.area, {"a.txt": b"a\n"})
        proc, _record = self.capture(repo, "work", py_cmd("print(1)"))
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        capture_dir = self.out_root / "work"
        listing = sorted(os.listdir(str(capture_dir)))
        forms = [str(capture_dir / "nested"), str(capture_dir).replace("\\", "/") + "/nested"]
        if os.name == "nt":
            forms.append(_ascii_swapcase(str(capture_dir / "nested")))
            forms.append(os.path.join(os.path.realpath(str(capture_dir)), "nested"))
        for dest in dict.fromkeys(forms):
            with self.subTest(dest=dest):
                proc = run_tool(["archive", str(capture_dir), "--dest", dest], repo)
                self.assertEqual(proc.returncode, 2, proc.stderr.decode("utf-8", "replace"))
                self.assertEqual(sorted(os.listdir(str(capture_dir))), listing)
        sibling = self.make_kelvin_sibling(capture_dir)
        proc = run_tool(["archive", str(capture_dir), "--dest", str(sibling)], repo)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        self.assertTrue((sibling / "work" / "archive-manifest.json").is_file())


# ---------------------------------------------------------------------------
# archive
# ---------------------------------------------------------------------------

class ArchiveTests(_AreaCase):
    def test_archive_redacts_repo_path_and_records_changes(self) -> None:
        repo = make_repo(self.area, {"a.txt": b"a\n"})
        code = "import os, sys; sys.stdout.buffer.write(b'\\xff\\xfe\\x00bin'); sys.stderr.write(os.getcwd())"
        proc, record = self.capture(repo, "ar1", py_cmd(code))
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        capture_dir = self.out_root / "ar1"
        toplevel = (capture_dir / "pre" / "02-rev-parse-toplevel.stdout.bin").read_bytes().decode("utf-8").strip()
        self.assertTrue(toplevel)
        dest = self.area.path / "archive"
        proc = run_tool(["archive", str(capture_dir), "--dest", str(dest)], repo)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        target = dest / "ar1"
        manifest = json.loads((target / "archive-manifest.json").read_bytes().decode("utf-8"))
        self.assertEqual(manifest["redaction"]["rule_revision"], "redact-v2")
        self.assertIs(manifest["redaction"]["values_recorded"], False)
        entries = {e["path"]: e for e in manifest["files"]}

        top = entries["pre/02-rev-parse-toplevel.stdout.bin"]
        self.assertEqual((target / top["path"]).read_bytes(), b"<REPO>\n")
        self.assertEqual(top["representation"], "redacted_raw")
        self.assertEqual(top["redaction_rule_revision"], "redact-v2")
        self.assertTrue(top["length_changed"])
        self.assertTrue(top["bytes_changed"])
        self.assertEqual(top["original_sha256"], sha256_of(capture_dir / top["path"]))
        self.assertEqual(top["archived_sha256"], sha256_of(target / top["path"]))
        self.assertEqual(top["replacements"]["<REPO>"], 1)

        stderr_entry = entries["run/stderr.bin"]  # os.getcwd() 的反斜杠写法
        self.assertEqual((target / "run" / "stderr.bin").read_bytes(), b"<REPO>")
        self.assertTrue(stderr_entry["length_changed"])

        raw = entries["run/stdout.bin"]
        self.assertEqual(raw["representation"], "captured_raw_copy")
        self.assertIsNone(raw["redaction_rule_revision"])
        self.assertFalse(raw["bytes_changed"])
        self.assertEqual((target / "run" / "stdout.bin").read_bytes(), b"\xff\xfe\x00bin")

        forms = {toplevel.lower(), toplevel.replace("/", "\\").lower(), toplevel.replace("/", "\\\\").lower()}
        for entry in manifest["files"]:
            if entry["representation"] != "redacted_raw":
                continue
            text = (target / entry["path"]).read_bytes().decode("utf-8").lower()
            for form in forms:
                self.assertNotIn(form, text, entry["path"])
        self.assertNotIn("archive-manifest.json", entries)
        self.assertEqual(sorted(entries), sorted(
            os.path.relpath(os.path.join(d, f), str(capture_dir)).replace("\\", "/")
            for d, _x, fs in os.walk(str(capture_dir)) for f in fs))

        before = sha256_of(target / "archive-manifest.json")
        again = run_tool(["archive", str(capture_dir), "--dest", str(dest)], repo)
        self.assertEqual(again.returncode, 1)
        self.assertEqual(sha256_of(target / "archive-manifest.json"), before)

    @unittest.skipUnless(os.name == "nt", "8.3 短名只在 Windows 上存在")
    def test_archive_redacts_8dot3_short_and_mixed_forms(self) -> None:
        # 回归：<HOME> 的 8.3 短名原样泄露，仓库根短名只被部分替换为 <TEMP>\CODEKI~1\REPODI~1。
        repo = make_repo(self.area, {"a.txt": b"a\n"}, name="repo directory long name")
        toplevel = git(repo, "rev-parse", "--show-toplevel").stdout.decode("utf-8").strip()
        repo_long = os.path.realpath(toplevel)
        repo_short = short_path(repo_long)
        if not repo_short or repo_short.lower() == repo_long.lower():
            self.skipTest("本卷没有为测试目录生成 8.3 短名")
        home_long = os.path.realpath(str(Path.home()))
        home_short = short_path(home_long) or home_long
        mixed = str(self.area.path / "repo directory long name")  # tempfile 给出的写法，可能只有部分分段是短名
        lines = [repo_short + "\\sub\\f.txt", repo_short.replace("\\", "/") + "/fwd.txt",
                 repo_short.replace("\\", "\\\\") + "\\\\json.txt", home_short + "\\Documents\\y",
                 mixed + "\\z"]
        command = [sys.executable, "-c",
                   "import sys; sys.stdout.buffer.write('\\n'.join(sys.argv[1:]).encode('utf-8'))"] + lines
        proc, _record = self.capture(repo, "ar3", command)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        dest = self.area.path / "archive"
        proc = run_tool(["archive", str(self.out_root / "ar3"), "--dest", str(dest)], repo)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        archived = (dest / "ar3" / "run" / "stdout.bin").read_bytes().decode("utf-8")
        self.assertEqual(archived.split("\n"), ["<REPO>\\sub\\f.txt", "<REPO>/fwd.txt", "<REPO>\\\\json.txt",
                                                "<HOME>\\Documents\\y", "<REPO>\\z"])
        short_parts = {part.lower() for text in (repo_short, home_short) for part in re.split(r"[\\/]", text)
                       if "~" in part}
        self.assertTrue(short_parts)
        for dirpath, _dirs, names in os.walk(str(dest / "ar3")):
            for name in names:
                data = Path(dirpath, name).read_bytes()
                try:
                    text = data.decode("utf-8").lower()
                except UnicodeDecodeError:
                    continue
                for part in short_parts:
                    self.assertNotIn(part, text, os.path.join(dirpath, name))
        manifest = json.loads((dest / "ar3" / "archive-manifest.json").read_bytes().decode("utf-8"))
        entry = {e["path"]: e for e in manifest["files"]}["run/stdout.bin"]
        self.assertEqual(entry["representation"], "redacted_raw")
        self.assertTrue(entry["length_changed"])
        self.assertEqual(entry["replacements"]["<REPO>"], 4)
        self.assertEqual(entry["replacements"]["<HOME>"], 1)

    def test_archive_refuses_capture_with_wrong_digest(self) -> None:
        repo = make_repo(self.area, {"a.txt": b"a\n"})
        proc, _record = self.capture(repo, "ar2", py_cmd("print(1)"))
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        with open(self.out_root / "ar2" / "run" / "stdout.bin", "ab") as handle:
            handle.write(b"tampered")
        dest = self.area.path / "archive"
        proc = run_tool(["archive", str(self.out_root / "ar2"), "--dest", str(dest)], repo)
        self.assertEqual(proc.returncode, 1)
        self.assertFalse((dest / "ar2").exists())

    def test_archive_redacts_bomless_utf16_instead_of_mislabeling_it(self) -> None:
        # 回归：无 BOM 的 UTF-16LE 能按 UTF-8 解码（NUL 合法），曾被标成 redacted_raw 却原样保留仓库路径。
        repo = make_repo(self.area, {"a.txt": b"a\n"})
        code = "import os, sys; sys.stderr.buffer.write(os.getcwd().encode('utf-16-le'))"
        proc, _record = self.capture(repo, "ar3", py_cmd(code))
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        dest = self.area.path / "archive"
        proc = run_tool(["archive", str(self.out_root / "ar3"), "--dest", str(dest)], repo)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        manifest = json.loads((dest / "ar3" / "archive-manifest.json").read_bytes().decode("utf-8"))
        entry = {e["path"]: e for e in manifest["files"]}["run/stderr.bin"]
        self.assertEqual(entry["text_encoding"], "utf-16-le")
        self.assertEqual(entry["representation"], "redacted_raw")
        self.assertEqual((dest / "ar3" / "run" / "stderr.bin").read_bytes(), "<REPO>".encode("utf-16-le"))
        self.assertNotIn("run/stderr.bin", manifest["unredacted_files"])


class TextEncodingTests(unittest.TestCase):
    def test_detects_utf16_and_keeps_nul_separated_utf8(self) -> None:
        self.assertEqual(baseline.text_encoding("C:\\repo\\x".encode("utf-16-le")), "utf-16-le")
        self.assertEqual(baseline.text_encoding("C:\\repo\\x".encode("utf-16-be")), "utf-16-be")
        # porcelain -z 这类 NUL 分隔的 UTF-8 不能被误判为 UTF-16
        self.assertEqual(baseline.text_encoding(" M a.txt\x00?? 中文 b.txt\x00".encode("utf-8")), "utf-8")
        self.assertIsNone(baseline.text_encoding(b"\xff\xfe\x00bin"))
        # 奇偶位置像 UTF-16 却解不出（孤立代理项）时不能退回 UTF-8 当成已脱敏
        self.assertIsNone(baseline.text_encoding(b"\x00\xd8a\x00b\x00c\x00"))


class ObjectFormatTests(_AreaCase):
    def test_echoed_unknown_option_is_not_recorded_as_object_format(self) -> None:
        # 回归：旧版 Git 会原样回显不认识的 --show-object-format 选项并返回 0。
        repo = make_repo(self.area, {"a.txt": b"a\n"})
        original = baseline.run_to_files

        def fake(ctx: Any, phase_dir: Path, cmd_id: str, argv: Any, executable: Any, env: Any) -> Any:
            if cmd_id == "04-rev-parse-object-format":
                argv = ["git", "rev-parse", "--show-object-format-unknown-to-this-git=storage"]
            return original(ctx, phase_dir, cmd_id, argv, executable, env)

        capture_dir = self.area.path / "of1"
        capture_dir.mkdir()
        ctx = baseline.CaptureContext(capture_dir, repo)
        baseline.run_to_files = fake
        try:
            sample = baseline.take_sample(ctx, "pre", base_env(), [".agent/baseline/"], shutil.which("git"),
                                          shutil.which("bash"))
        finally:
            baseline.run_to_files = original
        self.assertIsNone(sample["facts"]["object_format"])
        self.assertFalse(sample["complete"])
        self.assertTrue(any("对象格式" in p for p in sample["problems"]), sample["problems"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
