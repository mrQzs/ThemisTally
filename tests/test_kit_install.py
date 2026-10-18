# -*- coding: utf-8 -*-
"""执行器测试：scripts/kit_install.py（合同 kit-install.v1）。

oracle（tests/test_kit_install_oracle.py）已经覆盖三个命令的完整流程、冲突与备份、链接与记录；这里只补它没有
逐条钉住的部分：payload 的形状、CRLF 的 .gitattributes 只补缺少的规则、update 补回被删掉的文件、汇总的
counts、拒绝时的输出通道。全部经真实子进程驱动（payload 那一组除外，它直接导入模块）。
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path, PurePosixPath

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import kit_install as ki  # noqa: E402
import pi_dispatch as pd  # noqa: E402

STATUSES = ("ADD", "SAME", "UPDATE", "KEEP", "CONFLICT", "APPEND", "MANUAL", "REMOVED")
LINE_RE = re.compile(r"^(ADD|SAME|UPDATE|KEEP|CONFLICT|APPEND|MANUAL|REMOVED) (\S+)(?:  (.+))?$")
SUMMARY_KEYS = {"command", "target", "kit_root", "kit_version", "kit_commit", "counts", "unresolved", "backup",
                "record"}
RECORD = ".agent/kit-install.json"
#: kit 的 gitignore.append.txt：运行证据，加上 3.0 第二轮配置中心的本机状态（本机覆盖、写入历史与审计、配置锁）
IGNORE_RULES = (".agent/runs/", ".agent/dispatch.local.json", ".agent/config-history/", ".agent/audit/",
                ".agent/.config.lock/")
PROBE = "scripts/pi_dispatch.py"


class KitInstallTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kit-install-test-"))
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def make_target(self, name="target"):
        target = self.tmp / name
        target.mkdir()
        subprocess.run(["git", "init", "-q", str(target)], check=True)
        return target

    def run_kit(self, *args):
        env = dict(os.environ, PYTHONUTF8="1")
        proc = subprocess.run([sys.executable, str(REPO / "scripts" / "kit_install.py")] + [str(a) for a in args],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, timeout=180)
        lines = proc.stdout.decode("utf-8").splitlines()
        summary = json.loads(lines[-1]) if proc.returncode in (0, 1) else None
        rows = []
        for line in lines[:-1] if summary is not None else lines:
            match = LINE_RE.match(line)
            self.assertIsNotNone(match, "bad result line: %r" % line)
            rows.append(match.groups())
        return proc.returncode, rows, summary, proc.stderr.decode("utf-8", "replace")

    def row_of(self, rows, rel):
        found = [row for row in rows if row[1] == rel]
        self.assertEqual(len(found), 1, (rel, rows))
        return found[0]

    def record(self, target):
        return json.loads((target / RECORD).read_text(encoding="utf-8"))

    # ------------------------------------------------------------------ payload 的形状

    def test_payload_is_sorted_unique_relative_and_skips_the_non_payload_files(self):
        found = ki.payload(REPO)
        self.assertEqual(found, sorted(found), "payload 必须排序")
        self.assertEqual(len(found), len(set(found)), "payload 不得重复")
        for rel in found:
            self.assertNotIn("\\", rel)
            self.assertFalse(PurePosixPath(rel).is_absolute(), rel)
            self.assertTrue((REPO / rel).is_file(), rel)
        for entry in pd.KIT_LOADED_FILES:
            if not entry.endswith("/**"):
                self.assertIn(entry, found, entry)
        for skill in pd.KIT_SKILLS:
            self.assertTrue([rel for rel in found if rel.startswith("%s/%s/" % (pd.SKILL_SOURCE_DIR, skill))],
                            skill)
            self.assertTrue([rel for rel in found if rel.startswith("%s/%s/" % (pd.CLAUDE_SKILL_DIR, skill))],
                            skill)
        for absent in ("AGENTS.md", "scripts/kit_install.py", "gitignore.append.txt", "gitattributes.append.txt"):
            self.assertNotIn(absent, found, absent)
        self.assertFalse([rel for rel in found if "__pycache__" in rel or rel.endswith(".pyc")], found)

    # ------------------------------------------------------------------ 规则追加

    def test_gitattributes_with_crlf_and_one_rule_gets_only_the_missing_one(self):
        target = self.make_target()
        original = b"*.sh text eol=lf\r\n*.png binary"  # CRLF、末尾没有换行、已含其中一条规则
        (target / ".gitattributes").write_bytes(original)
        code, rows, summary, err = self.run_kit("install", target)
        self.assertEqual(code, 0, err)
        status, _rel, detail = self.row_of(rows, ".gitattributes")
        self.assertEqual(status, "APPEND")
        self.assertEqual(detail, "补上 .agent/** text eol=lf")
        data = (target / ".gitattributes").read_bytes()
        self.assertTrue(data.startswith(original), data)
        self.assertEqual(data, original + b"\n\n" + "# Code-Kit（kit_install.py 追加）\n.agent/** text eol=lf\n".encode())
        self.assertEqual((target / ".gitignore").read_bytes(),
                         ("# Code-Kit（kit_install.py 追加）\n" + "".join(rule + "\n" for rule in IGNORE_RULES)).encode())

    # ------------------------------------------------------------------ update 补回被删掉的文件

    def test_update_puts_back_a_deleted_payload_file(self):
        target = self.make_target()
        code, _rows, _summary, err = self.run_kit("install", target)
        self.assertEqual(code, 0, err)
        installed = self.record(target)["files"][PROBE]
        (target / PROBE).unlink()
        code, rows, summary, err = self.run_kit("update", target)
        self.assertEqual(code, 0, err)
        self.assertEqual(self.row_of(rows, PROBE)[0], "ADD")
        self.assertEqual((target / PROBE).read_bytes(), (REPO / PROBE).read_bytes())
        self.assertEqual(self.record(target)["files"][PROBE], installed)
        self.assertEqual(summary["unresolved"], [])

    # ------------------------------------------------------------------ 汇总

    def test_summary_counts_cover_every_status_and_every_row(self):
        target = self.make_target()
        code, rows, summary, err = self.run_kit("install", target)
        self.assertEqual(code, 0, err)
        self.assertEqual(set(summary), SUMMARY_KEYS)
        self.assertEqual(set(summary["counts"]), set(STATUSES))
        self.assertEqual(sum(summary["counts"].values()), len(rows))
        for status in STATUSES:
            self.assertEqual(summary["counts"][status], len([row for row in rows if row[0] == status]), status)
        self.assertGreater(summary["counts"]["ADD"], 0)
        self.assertEqual(summary["counts"]["APPEND"], 2)

    # ------------------------------------------------------------------ 拒绝

    def test_a_refusal_prints_nothing_on_stdout_and_one_error_line_on_stderr(self):
        target = self.make_target()
        code, _rows, _summary, err = self.run_kit("check", target)  # 合法基线（规划端补全，复审 F6）
        self.assertEqual(code, 0, err)
        proc = subprocess.run([sys.executable, str(REPO / "scripts" / "kit_install.py"), "install",
                               str(self.tmp / "missing")],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout.decode("utf-8"), "")
        stderr = proc.stderr.decode("utf-8", "replace")
        self.assertTrue(stderr.startswith("ERROR: "), stderr)
        self.assertEqual(len(stderr.strip().splitlines()), 1, stderr)
        self.assertEqual(sorted(path.name for path in target.iterdir()), [".git"])
        self.assertFalse((self.tmp / "missing").exists())


if __name__ == "__main__":
    unittest.main()
