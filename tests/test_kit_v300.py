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
        code, out, err = tool("plugins", "--help")
        self.assertEqual(code, 0, err)
        self.assertNotIn("Traceback", err)


if __name__ == "__main__":
    unittest.main()
