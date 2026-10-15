"""规划端 oracle：scripts/kit_install.py 的 check / install / update（Code-Kit 2.9，合同 kit-install.v1）。

全部经真实子进程 `python <kit>/scripts/kit_install.py …` 驱动。多数用例把 kit 的发放文件复制到临时目录当作
kit（这样能改 kit 来模拟升级、放进缓存文件）；最后一个用例用本仓库本身当 kit。目标仓库都是临时目录里
`git init` 出来的空仓库。不联网，不写本仓库。
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import pi_dispatch as pd  # noqa: E402

STATUSES = ("ADD", "SAME", "UPDATE", "KEEP", "CONFLICT", "APPEND", "MANUAL", "REMOVED")
LINE_RE = re.compile(r"^(ADD|SAME|UPDATE|KEEP|CONFLICT|APPEND|MANUAL|REMOVED) (\S+)(?:  (.+))?$")
SUMMARY_KEYS = {"command", "target", "kit_root", "kit_version", "kit_commit", "counts", "unresolved", "backup", "record"}
RECORD = ".agent/kit-install.json"
EXTRA_FILES = (".claude/agents/pi-reviewer.md", ".agent/README.md", ".agent/dispatch.config.example.json",
               ".codex/config.example.toml", ".claude/settings.example.json")
KIT_ONLY = ("scripts/kit_install.py", "AGENTS.md", "gitignore.append.txt", "gitattributes.append.txt")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def expected_payload(kit):
    """合同第 1 条：调度器与它加载的文件、四个技能的两份副本、五个示例与说明；不含 __pycache__ 与 .pyc。"""
    entries = ["scripts/pi_dispatch.py", "scripts/dispatch-pi.sh"] + list(pd.KIT_LOADED_FILES)
    for skill in pd.KIT_SKILLS:
        entries += ["%s/%s/**" % (pd.SKILL_SOURCE_DIR, skill), "%s/%s/**" % (pd.CLAUDE_SKILL_DIR, skill)]
    entries += list(EXTRA_FILES)
    found = set()
    for entry in entries:
        if not entry.endswith("/**"):
            found.add(entry)
            continue
        for dirpath, dirnames, filenames in os.walk(str(kit / entry[:-3])):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for name in filenames:
                if not name.endswith(".pyc"):
                    found.add((Path(dirpath) / name).relative_to(kit).as_posix())
    return sorted(found)


def tree_bytes(root):
    """目标仓库里 .git 之外的全部文件。"""
    out = {}
    for dirpath, dirnames, filenames in os.walk(str(root)):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for name in filenames:
            path = Path(dirpath) / name
            out[path.relative_to(root).as_posix()] = path.read_bytes()
    return out


def make_link(link, target):
    """目录链接。Windows 上先建 junction（它不是符号链接，只认符号链接的检查拦不住它），再试符号链接。"""
    if os.name == "nt":
        try:
            import _winapi
            _winapi.CreateJunction(str(target), str(link))
            return True
        except (OSError, ImportError, AttributeError):
            pass
    try:
        os.symlink(str(target), str(link), target_is_directory=True)
        return True
    except (OSError, NotImplementedError, AttributeError):
        return False


class KitInstallOracle(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kit-install-oracle-"))
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        for dirpath, dirnames, _files in os.walk(str(self.tmp)):
            for name in dirnames:  # 先拆掉测试建的链接，免得 rmtree 跟进去
                path = os.path.join(dirpath, name)
                if os.path.islink(path) or (os.name == "nt" and os.path.isdir(path) and _is_junction(path)):
                    try:
                        os.unlink(path)
                    except OSError:
                        os.rmdir(path)
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def make_kit(self):
        kit = self.tmp / "kit"
        for rel in expected_payload(REPO) + list(KIT_ONLY):
            (kit / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(str(REPO / rel), str(kit / rel))
        return kit

    def make_target(self, name="target"):
        target = self.tmp / name
        target.mkdir()
        subprocess.run(["git", "init", "-q", str(target)], check=True)
        return target

    def run_kit(self, kit, *args):
        env = dict(os.environ, PYTHONUTF8="1")
        proc = subprocess.run([sys.executable, str(kit / "scripts" / "kit_install.py")] + [str(a) for a in args],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, timeout=120)
        lines = proc.stdout.decode("utf-8").splitlines()
        summary = json.loads(lines[-1]) if proc.returncode in (0, 1) else None
        rows = []
        for line in lines[:-1] if summary is not None else lines:
            match = LINE_RE.match(line)
            self.assertIsNotNone(match, "bad result line: %r" % line)
            rows.append(match.groups())
        return proc.returncode, rows, summary, proc.stderr.decode("utf-8", "replace")

    def status_of(self, rows, rel):
        found = [row for row in rows if row[1] == rel]
        self.assertEqual(len(found), 1, (rel, rows))
        return found[0][0], found[0][2]

    def record(self, target):
        return json.loads((target / RECORD).read_text(encoding="utf-8"))

    # ------------------------------------------------------------------ install

    def test_fresh_install_writes_the_payload_byte_for_byte_and_nothing_else(self):
        kit, target = self.make_kit(), self.make_target()
        payload = expected_payload(kit)
        code, rows, summary, err = self.run_kit(kit, "install", target)
        self.assertEqual(code, 0, err)
        self.assertEqual(set(summary), SUMMARY_KEYS)
        self.assertEqual(summary["command"], "install")
        self.assertEqual(Path(summary["target"]), target.resolve())
        self.assertEqual(summary["kit_version"], pd.TOOL_VERSION)
        self.assertIsNone(summary["kit_commit"])
        self.assertEqual(summary["unresolved"], [])
        self.assertIsNone(summary["backup"])
        self.assertEqual(summary["record"], RECORD)
        self.assertEqual(set(summary["counts"]), set(STATUSES))
        self.assertEqual(summary["counts"]["ADD"], len(payload) + 2)
        self.assertEqual(summary["counts"]["APPEND"], 2)
        self.assertEqual(sum(summary["counts"].values()), len(rows))
        for rel in payload:
            self.assertEqual(self.status_of(rows, rel)[0], "ADD", rel)
            self.assertEqual((target / rel).read_bytes(), (kit / rel).read_bytes(), rel)
        self.assertEqual((target / "AGENTS.md").read_bytes(), (kit / "AGENTS.md").read_bytes())
        self.assertEqual((target / ".agent/dispatch.config.json").read_bytes(),
                         (kit / ".agent/dispatch.config.example.json").read_bytes())
        self.assertIn(".agent/runs/", (target / ".gitignore").read_text(encoding="utf-8").splitlines())
        attributes = (target / ".gitattributes").read_text(encoding="utf-8").splitlines()
        self.assertIn("*.sh text eol=lf", attributes)
        self.assertIn(".agent/** text eol=lf", attributes)
        record = self.record(target)
        self.assertEqual(record["record_type"], "code-kit-install")
        self.assertEqual(record["schema_version"], 1)
        self.assertEqual(record["kit_version"], pd.TOOL_VERSION)
        self.assertEqual(record["files"], {rel: sha((kit / rel).read_bytes()) for rel in payload})
        written = set(tree_bytes(target))
        self.assertEqual(written, set(payload) | {"AGENTS.md", ".agent/dispatch.config.json", ".gitignore",
                                                  ".gitattributes", RECORD})

    def test_check_is_read_only_and_reports_same_after_install(self):
        kit, target = self.make_kit(), self.make_target()
        code, rows, summary, err = self.run_kit(kit, "check", target)
        self.assertEqual(code, 0, err)
        self.assertEqual(tree_bytes(target), {})
        self.assertIsNone(summary["record"])
        self.assertEqual(summary["counts"]["ADD"], len(expected_payload(kit)) + 2)
        self.run_kit(kit, "install", target)
        before = tree_bytes(target)
        code, rows, summary, err = self.run_kit(kit, "check", target)
        self.assertEqual(code, 0, err)
        self.assertEqual(tree_bytes(target), before)
        self.assertEqual({row[0] for row in rows}, {"SAME"})
        self.assertEqual(summary["counts"]["SAME"], len(expected_payload(kit)) + 3)
        self.assertEqual(summary["record"], RECORD)
        code, rows, summary, err = self.run_kit(kit, "check", target, "--force")
        self.assertEqual(code, 2)
        self.assertEqual(tree_bytes(target), before)

    def test_a_second_install_is_refused_without_writing(self):
        kit, target = self.make_kit(), self.make_target()
        self.run_kit(kit, "install", target)
        (target / "scripts/pi_dispatch.py").write_bytes(b"local\n")
        before = tree_bytes(target)
        code, rows, summary, err = self.run_kit(kit, "install", target, "--force")
        self.assertEqual(code, 2)
        self.assertIn("update", err)
        self.assertEqual(tree_bytes(target), before)

    def test_an_existing_agents_md_is_left_alone_and_the_missing_sections_are_named(self):
        kit, target = self.make_kit(), self.make_target()
        mine = "# 我的规则\n\n## 角色判定\n\n自己的写法。\n".encode("utf-8")
        (target / "AGENTS.md").write_bytes(mine)
        code, rows, summary, err = self.run_kit(kit, "install", target)
        self.assertEqual(code, 0, err)
        self.assertEqual((target / "AGENTS.md").read_bytes(), mine)
        status, detail = self.status_of(rows, "AGENTS.md")
        self.assertEqual(status, "MANUAL")
        kit_heads = [line[3:].strip() for line in (kit / "AGENTS.md").read_text(encoding="utf-8").splitlines()
                     if line.startswith("## ")]
        self.assertEqual(detail, "缺少 kit 章节：" + "、".join(h for h in kit_heads if h != "角色判定"))
        self.assertEqual(summary["unresolved"], [])
        self.assertNotIn("AGENTS.md", self.record(target)["files"])
        (target / "AGENTS.md").write_bytes(mine + ("\n".join("## " + h for h in kit_heads) + "\n").encode("utf-8"))
        code, rows, summary, err = self.run_kit(kit, "check", target)
        self.assertEqual(self.status_of(rows, "AGENTS.md"), ("SAME", None))

    def test_a_different_file_is_a_conflict_until_force_and_force_keeps_a_backup(self):
        kit, target = self.make_kit(), self.make_target()
        (target / "scripts").mkdir()
        (target / "scripts/pi_dispatch.py").write_bytes(b"mine\n")
        code, rows, summary, err = self.run_kit(kit, "install", target)
        self.assertEqual(code, 1, err)
        self.assertEqual(self.status_of(rows, "scripts/pi_dispatch.py")[0], "CONFLICT")
        self.assertEqual(summary["unresolved"], ["scripts/pi_dispatch.py"])
        self.assertEqual((target / "scripts/pi_dispatch.py").read_bytes(), b"mine\n")
        self.assertNotIn("scripts/pi_dispatch.py", self.record(target)["files"])
        self.assertEqual((target / "scripts/dispatch-pi.sh").read_bytes(), (kit / "scripts/dispatch-pi.sh").read_bytes())
        code, rows, summary, err = self.run_kit(kit, "update", target, "--force")
        self.assertEqual(code, 0, err)
        status, detail = self.status_of(rows, "scripts/pi_dispatch.py")
        self.assertEqual(status, "UPDATE")
        self.assertTrue(summary["backup"].startswith(".agent/kit-backup/"), summary)
        self.assertEqual(detail, "--force：原文件备份到 %s/scripts/pi_dispatch.py" % summary["backup"])
        self.assertEqual((target / summary["backup"] / "scripts/pi_dispatch.py").read_bytes(), b"mine\n")
        self.assertEqual((target / "scripts/pi_dispatch.py").read_bytes(), (kit / "scripts/pi_dispatch.py").read_bytes())
        self.assertEqual(self.record(target)["files"]["scripts/pi_dispatch.py"],
                         sha((kit / "scripts/pi_dispatch.py").read_bytes()))

    def test_install_force_overwrites_a_conflict_on_first_install(self):
        kit, target = self.make_kit(), self.make_target()
        (target / "scripts").mkdir()
        (target / "scripts/kit_config.py").write_bytes(b"mine\n")
        code, rows, summary, err = self.run_kit(kit, "install", target, "--force")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.status_of(rows, "scripts/kit_config.py")[0], "UPDATE")
        self.assertEqual((target / summary["backup"] / "scripts/kit_config.py").read_bytes(), b"mine\n")
        self.assertEqual(summary["unresolved"], [])

    # ------------------------------------------------------------------ update

    def test_update_follows_the_kit_and_keeps_local_edits_until_force(self):
        kit, target = self.make_kit(), self.make_target()
        self.run_kit(kit, "install", target)
        upgraded, edited = ".agents/skills/review-pi/gates.md", ".agents/skills/plan-task/test-design.md"
        kit_edited = (kit / edited).read_bytes()
        (kit / upgraded).write_bytes((kit / upgraded).read_bytes() + b"\nkit change\n")
        (target / edited).write_bytes(kit_edited + b"\nlocal change\n")
        code, rows, summary, err = self.run_kit(kit, "check", target)
        self.assertEqual(code, 1, err)
        self.assertEqual(self.status_of(rows, upgraded)[0], "UPDATE")
        self.assertEqual(self.status_of(rows, edited)[0], "KEEP")
        code, rows, summary, err = self.run_kit(kit, "update", target)
        self.assertEqual(code, 1, err)
        self.assertEqual(summary["unresolved"], [edited])
        self.assertIsNone(summary["backup"])
        self.assertEqual((target / upgraded).read_bytes(), (kit / upgraded).read_bytes())
        self.assertEqual((target / edited).read_bytes(), kit_edited + b"\nlocal change\n")
        files = self.record(target)["files"]
        self.assertEqual(files[upgraded], sha((kit / upgraded).read_bytes()))
        self.assertEqual(files[edited], sha(kit_edited))
        code, rows, summary, err = self.run_kit(kit, "check", target)
        self.assertEqual(self.status_of(rows, edited)[0], "KEEP")
        self.assertEqual(self.status_of(rows, upgraded)[0], "SAME")
        code, rows, summary, err = self.run_kit(kit, "update", target, "--force")
        self.assertEqual(code, 0, err)
        self.assertEqual((target / edited).read_bytes(), kit_edited)
        self.assertEqual((target / summary["backup"] / edited).read_bytes(), kit_edited + b"\nlocal change\n")

    def test_update_adds_new_kit_files_and_reports_retired_ones_without_deleting(self):
        kit, target = self.make_kit(), self.make_target()
        self.run_kit(kit, "install", target)
        added = "plugins/decisions/questions/extra.json"
        (kit / added).write_bytes(b"{}\n")
        record = self.record(target)
        retired = "scripts/codekit/retired.py"
        (target / retired).write_bytes(b"old\n")
        record["files"][retired] = sha(b"old\n")
        (target / RECORD).write_text(json.dumps(record), encoding="utf-8")
        code, rows, summary, err = self.run_kit(kit, "update", target)
        self.assertEqual(code, 0, err)
        self.assertEqual(self.status_of(rows, added)[0], "ADD")
        self.assertEqual((target / added).read_bytes(), b"{}\n")
        status, detail = self.status_of(rows, retired)
        self.assertEqual(status, "REMOVED")
        self.assertTrue(detail)
        self.assertEqual((target / retired).read_bytes(), b"old\n")
        files = self.record(target)["files"]
        self.assertNotIn(retired, files)
        self.assertEqual(files[added], sha(b"{}\n"))

    def test_update_without_a_record_is_refused(self):
        kit, target = self.make_kit(), self.make_target()
        code, rows, summary, err = self.run_kit(kit, "update", target)
        self.assertEqual(code, 2)
        self.assertIn("install", err)
        self.assertEqual(tree_bytes(target), {})

    # ------------------------------------------------------------------ what is not copied, what is appended

    def test_caches_are_not_installed(self):
        kit, target = self.make_kit(), self.make_target()
        (kit / "plugins/decisions/__pycache__").mkdir()
        (kit / "plugins/decisions/__pycache__/x.cpython-312.pyc").write_bytes(b"\0")
        (kit / "plugins/decisions/__pycache__/notes.txt").write_bytes(b"cache\n")  # 只有目录规则拦得住它
        (kit / ".agents/skills/plan-task/stray.pyc").write_bytes(b"\0")
        code, rows, summary, err = self.run_kit(kit, "install", target)
        self.assertEqual(code, 0, err)
        written = tree_bytes(target)
        self.assertFalse([rel for rel in written if "__pycache__" in rel or rel.endswith(".pyc")], sorted(written))

    def test_ignore_rules_are_appended_once_and_existing_content_is_kept(self):
        kit, target = self.make_kit(), self.make_target()
        original = b"node_modules/\r\n*.log"
        (target / ".gitignore").write_bytes(original)
        (target / ".gitattributes").write_bytes(b"*.sh text eol=lf\n.agent/** text eol=lf\n")
        code, rows, summary, err = self.run_kit(kit, "install", target)
        self.assertEqual(code, 0, err)
        self.assertEqual(self.status_of(rows, ".gitignore"), ("APPEND", "补上 .agent/runs/"))
        self.assertEqual(self.status_of(rows, ".gitattributes")[0], "SAME")
        data = (target / ".gitignore").read_bytes()
        self.assertTrue(data.startswith(original), data)
        self.assertEqual(data, original + "\n\n# Code-Kit（kit_install.py 追加）\n.agent/runs/\n".encode("utf-8"))
        self.assertEqual((target / ".gitattributes").read_bytes(), b"*.sh text eol=lf\n.agent/** text eol=lf\n")
        code, rows, summary, err = self.run_kit(kit, "check", target)
        self.assertEqual(self.status_of(rows, ".gitignore")[0], "SAME")

    def test_an_existing_dispatch_config_is_never_touched(self):
        kit, target = self.make_kit(), self.make_target()
        (target / ".agent").mkdir()
        (target / ".agent/dispatch.config.json").write_bytes(b'{"mine": true}\n')
        code, rows, summary, err = self.run_kit(kit, "install", target)
        self.assertEqual(code, 0, err)
        self.assertEqual((target / ".agent/dispatch.config.json").read_bytes(), b'{"mine": true}\n')
        self.assertFalse([row for row in rows if row[1] == ".agent/dispatch.config.json"], rows)

    # ------------------------------------------------------------------ refusals

    def test_refusals_write_nothing(self):
        kit, target = self.make_kit(), self.make_target()
        (target / "sub").mkdir()
        code, rows, summary, err = self.run_kit(kit, "install", target / "sub")
        self.assertEqual(code, 2)
        self.assertEqual(tree_bytes(target), {})
        code, rows, summary, err = self.run_kit(kit, "install", self.tmp / "missing")
        self.assertEqual(code, 2)
        subprocess.run(["git", "init", "-q", str(kit)], check=True)
        before = tree_bytes(kit)
        code, rows, summary, err = self.run_kit(kit, "install", kit)
        self.assertEqual(code, 2)
        self.assertEqual(tree_bytes(kit), before)
        code, rows, summary, err = self.run_kit(kit, "uninstall", target)
        self.assertEqual(code, 2)

    def test_links_in_the_target_are_refused_before_anything_is_written(self):
        kit, target = self.make_kit(), self.make_target()
        outside = self.tmp / "outside"
        outside.mkdir()
        if not make_link(target / "scripts", outside):
            self.skipTest("cannot create a directory link here")
        code, rows, summary, err = self.run_kit(kit, "install", target)
        self.assertEqual(code, 2)
        self.assertEqual(list(outside.iterdir()), [])
        self.assertFalse((target / RECORD).exists())
        self.assertFalse((target / "AGENTS.md").exists())

    def test_links_in_the_kit_are_refused(self):
        kit, target = self.make_kit(), self.make_target()
        outside = self.tmp / "outside"
        outside.mkdir()
        (outside / "secret.md").write_bytes(b"outside\n")
        if not make_link(kit / ".agents/skills/review-pi/linked", outside):
            self.skipTest("cannot create a directory link here")
        code, rows, summary, err = self.run_kit(kit, "install", target)
        self.assertEqual(code, 2)
        self.assertEqual(tree_bytes(target), {})

    # ------------------------------------------------------------------ the real kit

    def test_the_real_kit_reports_its_commit(self):
        target = self.make_target()
        code, rows, summary, err = self.run_kit(REPO, "check", target)
        self.assertEqual(code, 0, err)
        head = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], stdout=subprocess.PIPE,
                              check=True).stdout.decode().strip()
        self.assertEqual(summary["kit_commit"], head)
        self.assertEqual(Path(summary["kit_root"]), REPO)
        self.assertEqual(summary["counts"]["ADD"], len(expected_payload(REPO)) + 2)
        self.assertEqual(tree_bytes(target), {})


def _is_junction(path):
    try:
        return bool(os.lstat(path).st_file_attributes & 0x400)
    except (OSError, AttributeError):
        return False


if __name__ == "__main__":
    unittest.main()
