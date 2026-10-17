"""Code-Kit 2.8.0 的单元测试：问题清单的内容锁、kit 自己加载的文件受保护、变异清单的多条命令与预期、锚点提示。

端到端的部分（integrate、review-draft、mutate 多命令、prepare 遇到锁不符）在 tests/test_dispatch.py 的 test_v280_*。
"""
import ast
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import pi_dispatch as pd  # noqa: E402
from codekit import decisions as d  # noqa: E402

PLUGIN = ROOT / "plugins" / "decisions"


def _tmpdir(case: unittest.TestCase) -> Path:
    path = Path(tempfile.mkdtemp(prefix="codekit-v280-"))
    case.addCleanup(shutil.rmtree, str(path), True)
    return path


class BatteryLock(unittest.TestCase):
    def copy_plugin(self) -> Path:
        target = _tmpdir(self) / "plugins" / "decisions"
        shutil.copytree(str(PLUGIN), str(target))
        return target

    def test_the_shipped_plugin_verifies(self):
        self.assertEqual(sorted(d.verify_battery_lock(PLUGIN)),
                         ["mutation-equivalence.json", "report-screen.json", "run-health.json"])
        self.assertEqual(set(d.load_locked_batteries(PLUGIN)), {"mutation-equivalence", "report-screen", "run-health"})

    def test_a_changed_battery_is_drift_and_names_the_fix(self):
        plugin = self.copy_plugin()
        path = plugin / "questions" / "report-screen.json"
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaises(d.DecisionError) as caught:
            d.load_locked_batteries(plugin)
        self.assertEqual(caught.exception.code, "battery_drift")
        self.assertIn("report-screen.json differs from the locked bytes", caught.exception.detail)
        self.assertNotIn("line endings", caught.exception.detail)
        self.assertIn("--write-lock", caught.exception.detail)

    def test_a_crlf_checkout_is_named_as_such(self):
        plugin = self.copy_plugin()
        path = plugin / "questions" / "run-health.json"
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
        with self.assertRaises(d.DecisionError) as caught:
            d.verify_battery_lock(plugin)
        self.assertIn("only in line endings", caught.exception.detail)

    def test_extra_and_missing_batteries_are_drift(self):
        plugin = self.copy_plugin()
        shutil.copy(str(plugin / "questions" / "run-health.json"), str(plugin / "questions" / "extra.json"))
        (plugin / "questions" / "mutation-equivalence.json").unlink()
        with self.assertRaises(d.DecisionError) as caught:
            d.verify_battery_lock(plugin)
        self.assertIn("extra.json is not in the lock", caught.exception.detail)
        self.assertIn("mutation-equivalence.json is locked but missing", caught.exception.detail)

    def test_an_unreadable_battery_is_drift_not_an_oserror(self):
        # 3.0 第一轮：调用方（kit_config、doctor、load_locked_batteries）都只捕获 DecisionError
        plugin = self.copy_plugin()
        path = plugin / "questions" / "run-health.json"
        path.unlink()
        path.mkdir()
        with self.assertRaises(d.DecisionError) as caught:
            d.verify_battery_lock(plugin)
        self.assertEqual(caught.exception.code, "battery_drift")
        self.assertIn("run-health.json cannot be read", caught.exception.detail)

    def test_a_hand_edited_lock_does_not_verify(self):
        plugin = self.copy_plugin()
        lock = json.loads((plugin / "lock.json").read_text(encoding="utf-8"))
        lock["plugins"][0]["resources"][0]["sha256"] = "0" * 64
        (plugin / "lock.json").write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        with self.assertRaises(d.DecisionError) as caught:
            d.verify_battery_lock(plugin)
        self.assertIn("lock does not verify", caught.exception.detail)

    def test_write_lock_reproduces_the_shipped_bytes_and_takes_a_reviewed_change(self):
        plugin = self.copy_plugin()
        before = {name: (plugin / name).read_bytes() for name in ("manifest.json", "lock.json")}
        d.write_lock(plugin)
        self.assertEqual(before, {name: (plugin / name).read_bytes() for name in before})
        path = plugin / "questions" / "run-health.json"
        battery = json.loads(path.read_text(encoding="utf-8"))
        battery["description"] = str(battery.get("description", "")) + " (reviewed change)"
        path.write_text(json.dumps(battery, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        with self.assertRaises(d.DecisionError):
            d.verify_battery_lock(plugin)
        d.write_lock(plugin)
        self.assertIn("run-health.json", d.verify_battery_lock(plugin))
        self.assertNotEqual(before["lock.json"], (plugin / "lock.json").read_bytes())

    def test_write_lock_refuses_an_invalid_battery_and_leaves_the_lock(self):
        plugin = self.copy_plugin()
        (plugin / "questions" / "broken.json").write_text('{"id": "broken"}', encoding="utf-8")
        before = (plugin / "lock.json").read_bytes()
        with self.assertRaises(d.DecisionError):
            d.write_lock(plugin)
        self.assertEqual(before, (plugin / "lock.json").read_bytes())

    def test_the_command_line_checks_the_lock(self):
        plugin = self.copy_plugin()
        self.assertEqual(d.main(["--check-lock", str(plugin)]), 0)
        (plugin / "questions" / "report-screen.json").write_bytes(b"{}")
        self.assertEqual(d.main(["--check-lock", str(plugin)]), 1)

    def test_describe_reports_the_lock_state(self):
        settings = d.settings_from_config({}, None, PLUGIN)
        self.assertEqual(d.describe(settings, PLUGIN, environ={})["battery_lock"], "ok")
        plugin = self.copy_plugin()
        (plugin / "questions" / "report-screen.json").write_bytes(b"{}")
        facts = d.describe(settings, plugin, environ={})
        self.assertEqual(facts["battery_lock"], "drift")
        self.assertTrue(any("battery_drift" in problem for problem in facts["battery_problems"]))


class KitLoadedFiles(unittest.TestCase):
    """调度器与配置管理器会加载的 kit 文件都受保护；v2 参考实现的其余模块不在其列（2.8.0）。"""

    def test_the_protected_list_matches_what_the_dispatcher_imports(self):
        scripts = ROOT / "scripts"
        seen = set()
        queue = [scripts / "pi_dispatch.py", scripts / "kit_config.py"]
        while queue:
            path = queue.pop()
            if path in seen:
                continue
            seen.add(path)
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                targets = []
                if isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    if node.level:
                        targets += ([path.parent / (module.replace(".", "/") + ".py")] if module
                                    else [path.parent / (alias.name + ".py") for alias in node.names])
                    elif module in ("codekit", "scripts.codekit"):
                        targets += [scripts / "codekit" / (alias.name + ".py") for alias in node.names]
                    elif ".codekit." in "." + module + "." and module.split("codekit.", 1)[1:]:
                        targets.append(scripts / "codekit" / (module.split("codekit.", 1)[1].replace(".", "/") + ".py"))
                elif isinstance(node, ast.Import):
                    # pi_dispatch 与 kit_<名>（配置、日志、插件管理；3.0 第一轮 D8 的转发也是 import kit_<名>），
                    # 只跟随 scripts/ 下真实存在的文件。
                    targets += [scripts / (alias.name + ".py") for alias in node.names
                                if alias.name == "pi_dispatch" or alias.name.startswith("kit_")]
                queue += [target for target in targets if target.is_file()]
        loaded = {path.relative_to(ROOT).as_posix() for path in seen} - {"scripts/pi_dispatch.py"}
        loaded.add("scripts/codekit/__init__.py")
        listed = {item for item in pd.KIT_LOADED_FILES if not item.endswith("/**")}
        self.assertEqual(listed, loaded)
        self.assertIn("plugins/decisions/**", pd.KIT_LOADED_FILES)

    def test_kit_files_are_protected_and_the_rest_of_codekit_is_not(self):
        protected = pd.compile_patterns(list(pd.PROTECTED_PATTERNS), ignore_case=True)
        for path in ("scripts/kit_config.py", "scripts/codekit/decisions.py", "scripts/codekit/plugins.py",
                     "scripts/codekit/secrets.py", "plugins/decisions/questions/report-screen.json",
                     "plugins/decisions/lock.json", "scripts/pi_dispatch.py", "Scripts/CodeKit/Decisions.py"):
            self.assertTrue(pd.matches(protected, path), path)
        for path in ("scripts/codekit/workflow.py", "plugins/mutation-review/lock.json", "src/plugins/decisions.py"):
            self.assertFalse(pd.matches(protected, path), path)


class MutationSpec(unittest.TestCase):
    def load(self, spec):
        path = _tmpdir(self) / "spec.json"
        path.write_text(json.dumps(spec), encoding="utf-8")
        return pd._load_mutation_spec(path)

    def item(self, name="a", **extra):
        return dict({"name": name, "file": "f.py", "old": "x", "new": "y"}, **extra)

    def test_commands_with_expectations(self):
        spec, problems = self.load({
            "commands": [{"id": "all", "argv": ["python", "a"]}, {"id": "executor", "argv": ["python", "b"],
                                                                  "timeout_seconds": 30, "cwd": "tests"}],
            "timeout_seconds": 60,
            "mutations": [self.item("a", expect_missed=["executor"]), self.item("b", new="z", equivalent="same")]})
        self.assertEqual(problems, [])
        self.assertEqual([(c["id"], c["timeout_seconds"], c["cwd"]) for c in spec["_commands"]],
                         [("all", 60, "."), ("executor", 30, "tests")])
        first, second = spec["mutations"]
        self.assertEqual(pd._mutation_expected(first, "executor"), "missed")
        self.assertEqual(pd._mutation_expected(first, "all"), "caught")
        self.assertEqual(pd._mutation_expected(second, "all"), "missed")
        self.assertTrue(pd._spec_has_expectations(spec))

    def test_a_single_command_is_main(self):
        spec, problems = self.load({"command": ["python", "t.py"], "mutations": [self.item()]})
        self.assertEqual(problems, [])
        self.assertEqual(spec["_commands"], [{"id": "main", "argv": ["python", "t.py"], "cwd": ".",
                                              "timeout_seconds": pd.MUTATION_DEFAULT_TIMEOUT}])
        self.assertFalse(pd._spec_has_expectations(spec))

    def test_problems_are_reported(self):
        cases = [
            ({"command": ["p"], "commands": [{"id": "a", "argv": ["p"]}], "mutations": [self.item()]}, "只能写一个"),
            ({"commands": [{"id": "a", "argv": ["p"]}, {"id": "a", "argv": ["q"]}], "mutations": [self.item()]}, "重复"),
            ({"commands": [{"id": "1a", "argv": ["p"]}], "mutations": [self.item()]}, "commands[1].id"),
            ({"commands": [{"id": "a", "argv": []}], "mutations": [self.item()]}, "commands[1].argv"),
            ({"commands": [{"id": "a", "argv": ["p"], "shell": True}], "mutations": [self.item()]}, "只含"),
            ({"commands": [], "mutations": [self.item()]}, "1 到"),
            ({"commands": [{"id": "a", "argv": ["p"]}], "mutations": [self.item(expect_missed=["b"])]}, "没有的命令"),
            ({"command": ["p"], "mutations": [self.item(expect_missed=[])]}, "expect_missed"),
            ({"command": ["p"], "mutations": [self.item(equivalent=" ")]}, "equivalent"),
            ({"command": ["p"], "mutations": [self.item(equivalent="same", expect_missed=["main"])]}, "同时写了"),
        ]
        for spec, expected in cases:
            _spec, problems = self.load(spec)
            self.assertTrue(any(expected in problem for problem in problems), (spec, problems))


class AnchorHints(unittest.TestCase):
    def test_nearest_lines_and_every_occurrence(self):
        path = _tmpdir(self) / "m.py"
        path.write_bytes(b"def f(q):\r\n    return q.lower()\r\n\r\ndef g(q):\r\n    return q.lower()\r\n    # end\r\n")
        hints = pd._anchor_hints(path, "    return q.upper()\n", 0)
        self.assertTrue(hints[0].startswith("最相近 L2"), hints)
        self.assertEqual(pd._anchor_hints(path, "zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz", 0), ["文件里没有相近的行"])
        hints = pd._anchor_hints(path, "return q.lower()", 2)
        self.assertEqual([hint.split("；")[0] for hint in hints], ["出现在 L2", "出现在 L5"])
        self.assertIn("（空行）", hints[0])
        self.assertIn("# end", hints[1])


if __name__ == "__main__":
    unittest.main()
