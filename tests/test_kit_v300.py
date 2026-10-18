# -*- coding: utf-8 -*-
"""3.0 第一轮：logs、plugins 接入调度器（docs/themis-tally-3.0-r1-日志与插件管理.md 的 D8，测试计划 W1、W2）。

W1 在进程内调用 pi_dispatch.main，用替身模块记录下游 main 收到的参数与 repo；W2 用 kit_install 装进临时目标仓库，
经真实子进程运行装好的命令。设计原把它们写在 tests/test_dispatch.py，但那里的 check() 不抛异常，pytest 下失败也
显示为通过，所以改成独立的 unittest 模块（设计 §0 impl-4）。
"""
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import pi_dispatch as pd  # noqa: E402

NEW_FILES = ("scripts/kit_logs.py", "scripts/kit_plugins.py")


class Forwarding(unittest.TestCase):
    """W1：logs、plugins 在 argparse 之前截获，参数原样转发，下游的退出码原样返回。"""

    def setUp(self):
        self.downstream = {}
        modules = {}
        for name in ("kit_logs", "kit_plugins"):
            fake = types.ModuleType(name)
            fake.main = mock.Mock(return_value=7)
            modules[name] = fake
            self.downstream[name] = fake.main
        patcher = mock.patch.dict(sys.modules, modules)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_main(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = pd.main(argv)
            except SystemExit as exc:
                code = exc.code
        return code, out.getvalue(), err.getvalue()

    def assertNotForwarded(self):
        for name, main in self.downstream.items():
            self.assertEqual(main.call_count, 0, name)

    def test_arguments_are_forwarded_verbatim_and_the_exit_code_comes_back(self):
        cases = [
            (["plugins", "--help"], "kit_plugins", ["--help"], None),
            (["plugins", "list", "--json"], "kit_plugins", ["list", "--json"], None),
            (["logs", "--repo", "R", "list"], "kit_logs", ["--repo", "R", "list"], None),
            (["--repo", "R", "plugins", "list"], "kit_plugins", ["list"], "R"),
            (["--repo=R", "logs", "show", "task-a"], "kit_logs", ["show", "task-a"], "R"),
            # 全局与下游各给一个 --repo：下游的留在参数里，由下游 main 决定优先（与 kit_config 相同）
            (["--repo", "A", "plugins", "--repo", "B", "list"], "kit_plugins", ["--repo", "B", "list"], "A"),
            (["--repo", "A", "--repo", "B", "logs", "list"], "kit_logs", ["list"], "B"),
            (["logs"], "kit_logs", [], None),
        ]
        for argv, module, args, repo in cases:
            with self.subTest(argv=argv):
                for main in self.downstream.values():
                    main.reset_mock()
                code, out, err = self.run_main(argv)
                self.assertEqual(code, 7, (out, err))
                self.downstream[module].assert_called_once_with(args, repo=repo)
                other = "kit_logs" if module == "kit_plugins" else "kit_plugins"
                self.assertEqual(self.downstream[other].call_count, 0)

    def test_version_and_help_before_the_command_are_left_to_argparse(self):
        code, out, _ = self.run_main(["--version", "plugins", "list"])
        self.assertEqual(code, 0)
        self.assertIn("pi_dispatch", out)
        code, out, _ = self.run_main(["-h", "plugins"])
        self.assertEqual(code, 0)
        self.assertIn("usage:", out)
        self.assertNotForwarded()

    def test_other_options_or_a_missing_repo_value_go_to_argparse(self):
        for argv in (["--unknown", "plugins", "list"], ["--", "plugins", "list"], ["--repo"],
                     ["--repo", "--version"], ["--repo=", "plugins", "list"], ["--repo", "", "plugins", "list"],
                     ["--rep", "R", "plugins", "list"]):
            with self.subTest(argv=argv):
                code, out, err = self.run_main(argv)
                self.assertEqual(code, pd.EXIT_USAGE, (out, err))
                self.assertNotForwarded()

    def test_another_command_mentioning_plugins_is_not_forwarded(self):
        with mock.patch.object(pd, "cmd_doctor", return_value=0) as doctor:
            code, out, err = self.run_main(["doctor", "--out", "plugins"])
        self.assertEqual(code, 0, (out, err))
        self.assertEqual(doctor.call_args[0][0].out, "plugins")
        self.assertNotForwarded()

    def test_a_missing_module_is_a_usage_error_without_a_traceback(self):
        with mock.patch.dict(sys.modules, {"kit_logs": None, "kit_plugins": None}):
            for argv, needle in ((["plugins", "list"], "scripts/kit_plugins.py"),
                                 (["logs", "list"], "scripts/kit_logs.py")):
                with self.subTest(argv=argv):
                    code, _, err = self.run_main(argv)
                    self.assertEqual(code, pd.EXIT_USAGE)
                    self.assertIn("ERROR:", err)
                    self.assertIn(needle, err)
                    self.assertNotIn("Traceback", err)

    def test_help_lists_both_commands(self):
        code, out, _ = self.run_main(["--help"])
        self.assertEqual(code, 0)
        self.assertIn("config,logs,plugins,", out)  # 子命令清单（argparse 按终端宽度折行，只比较不会折开的片段）
        self.assertIn("日志管理（只读）", out)
        self.assertIn("插件管理：list", out)
        self.assertNotForwarded()


class LinkPredicateInputs(unittest.TestCase):
    """is_link_or_junction 是谓词：含 NUL 或编码不了的路径不是链接，不抛异常（Windows 上 os.lstat 会抛 ValueError）。"""

    def test_unrepresentable_paths_are_not_links(self):
        tmp = Path(tempfile.mkdtemp(prefix="kit-v300-link-"))
        self.addCleanup(shutil.rmtree, str(tmp), True)
        for path in ("a\x00b", str(tmp / "x\x00y"), tmp / "x\x00y", "\ud800"):
            with self.subTest(path=ascii(path)):
                self.assertFalse(pd.is_link_or_junction(path))
        self.assertIsNone(pd.first_link_component(tmp, "x\x00y/z"))


class RepoArgument(unittest.TestCase):
    """闸二 B3：--repo 指向文件时一行 ERROR、退出 2，不冒 NotADirectoryError 的堆栈（所有命令共用 Repo.discover）。"""

    def test_repo_pointing_at_a_file_is_a_usage_error(self):
        target = ROOT / "README.md"
        env = dict(os.environ, PYTHONUTF8="1", CODEKIT_SECRET_STORE="off")
        for argv in (["status"], ["logs", "list"], ["plugins", "list"]):
            with self.subTest(argv=argv):
                proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "pi_dispatch.py"), "--repo", str(target)]
                                      + argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, timeout=120)
                err = proc.stderr.decode("utf-8", "replace")
                self.assertEqual(proc.returncode, 2, err)
                self.assertIn("ERROR:", err)
                self.assertNotIn("Traceback", err)


class InstalledLayout(unittest.TestCase):
    """W2：两个新文件受保护、随 kit 发放；装进目标仓库后，装好的 logs 与 plugins 能用（安装布局只有决策插件）。"""

    def test_new_files_are_loaded_kit_files_and_protected(self):
        protected = pd.compile_patterns(list(pd.PROTECTED_PATTERNS), ignore_case=True)
        for rel in NEW_FILES:
            self.assertIn(rel, pd.KIT_LOADED_FILES)
            self.assertTrue(pd.matches(protected, rel), rel)

    def test_installed_commands_run_in_the_target(self):
        tmp = Path(tempfile.mkdtemp(prefix="kit-v300-"))
        self.addCleanup(shutil.rmtree, str(tmp), True)
        target = tmp / "target"
        target.mkdir()
        subprocess.run(["git", "init", "-q", str(target)], check=True)
        env = dict(os.environ, PYTHONUTF8="1", CODEKIT_SECRET_STORE="off")
        proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "kit_install.py"), "install", str(target)],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, timeout=180)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        for rel in NEW_FILES:
            self.assertTrue((target / rel).is_file(), rel)
        self.assertEqual(sorted(p.name for p in (target / "plugins").iterdir()), ["decisions"])

        def tool(*args):
            done = subprocess.run([sys.executable, "scripts/pi_dispatch.py"] + list(args), cwd=str(target),
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, timeout=180)
            return done.returncode, done.stdout.decode("utf-8"), done.stderr.decode("utf-8", "replace")

        code, out, err = tool("logs", "list", "--json")
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["attempts"], [])
        code, out, err = tool("plugins", "list", "--json")
        self.assertEqual(code, 0, err)
        self.assertIn("decisions", out)
        self.assertNotIn("code-change", out)
        # 闸二补强：装好的决策插件核对一致、状态 READY（不只是列出了 ID）
        code, out, err = tool("plugins", "list")
        self.assertEqual(code, 0, err)
        row = [line for line in out.splitlines() if line.split()[:1] == ["decisions"]]
        self.assertEqual(len(row), 1, out)
        self.assertIn("READY", row[0])
        self.assertIn("锁:一致", row[0])
        code, out, err = tool("plugins", "--help")
        self.assertEqual(code, 0, err)
        self.assertNotIn("Traceback", err)


def _dir_link(link, target):
    """建指向目录的链接：Windows 上用 junction（mklink /J 不需要权限），其它平台用符号链接；建不了返回 False。"""
    if os.name == "nt":
        return subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True).returncode == 0
    try:
        os.symlink(str(target), str(link), target_is_directory=True)
    except OSError:
        return False
    return True


class RunDirBoundary(unittest.TestCase):
    """第一轮设计第 10 节第 5 项：task-id 与 task-id.vN 也不跟随链接，结果必须在 runs 之下（原来直接返回 resolve() 的结果）。"""

    def setUp(self):
        tmp = Path(tempfile.mkdtemp(prefix="kit-v300-rundir-"))
        self.addCleanup(shutil.rmtree, str(tmp), True)
        self.root = tmp / "repo"
        self.root.mkdir()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.repo = pd.Repo.discover(str(self.root))
        self.outside = tmp / "outside"
        for attempt in (self.repo.runs_dir / "t1" / "attempt-001", self.outside / "attempt-001"):
            attempt.mkdir(parents=True)
            (attempt / "meta.json").write_text(json.dumps({"plan_version": 1}), encoding="utf-8")

    def link(self, link, target):
        if not _dir_link(link, target):
            self.skipTest("建不了目录链接")

    def assertRefused(self, value):
        with self.assertRaises(pd.DispatchError) as caught:
            pd.resolve_run_dir(self.repo, value)
        self.assertEqual(caught.exception.code, pd.EXIT_USAGE)
        self.assertIn("链接", str(caught.exception))

    def test_plain_attempts_still_resolve(self):
        expected = (self.repo.runs_dir / "t1" / "attempt-001").resolve()
        self.assertEqual(pd.resolve_run_dir(self.repo, "t1"), expected)
        self.assertEqual(pd.resolve_run_dir(self.repo, "t1.v1"), expected)

    def test_latest_attempt_that_is_a_link_is_refused(self):
        self.link(self.repo.runs_dir / "t1" / "attempt-002", self.outside / "attempt-001")
        self.assertRefused("t1")
        self.assertRefused("t1.v1")

    def test_version_lookup_does_not_read_through_a_link(self):
        # 链接的编号比真实的小：只取最新的 task-id 形式照常解析；按版本筛选要读 meta.json，所以停下，且不读链接后面的文件。
        real = self.repo.runs_dir / "t1" / "attempt-001"
        shutil.move(str(real), str(self.repo.runs_dir / "t1" / "attempt-005"))
        self.link(real, self.outside / "attempt-001")
        self.assertEqual(pd.resolve_run_dir(self.repo, "t1"), (self.repo.runs_dir / "t1" / "attempt-005").resolve())
        reads = []
        original = pd.read_json_or

        def spy(path, default):
            reads.append(Path(path))
            return original(path, default)

        with mock.patch.object(pd, "read_json_or", spy):
            self.assertRefused("t1.v1")
        self.assertFalse([p for p in reads if "attempt-001" in p.as_posix()], reads)

    def test_task_directory_that_is_a_link_is_refused(self):
        self.link(self.repo.runs_dir / "t2", self.outside)
        self.assertRefused("t2")
        self.assertRefused("t2.v1")

    def test_cli_reports_one_error_line(self):
        self.link(self.repo.runs_dir / "t1" / "attempt-002", self.outside / "attempt-001")
        env = dict(os.environ, PYTHONUTF8="1", CODEKIT_SECRET_STORE="off")
        proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "pi_dispatch.py"), "--repo", str(self.root),
                               "mark", "t1", "ABANDONED", "--reason", "x"], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, env=env, timeout=120)
        err = proc.stderr.decode("utf-8", "replace")
        self.assertEqual(proc.returncode, 2, err)
        self.assertIn("不跟随", err)
        self.assertNotIn("Traceback", err)
        self.assertFalse((self.outside / "attempt-001" / "state.json").exists())


if __name__ == "__main__":
    unittest.main()
