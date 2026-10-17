"""scripts/kit_config.py 与 scripts/codekit/secrets.py 的离线测试（2.7.0）。

没有网络、不碰真实凭据库：凭据后端用文件后端（临时 XDG_CONFIG_HOME）或假的 advapi32；一次性网页用本机
HTTP 客户端访问；决策模型用假传输。配置命令在临时 Git 仓库上跑。
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import kit_config  # noqa: E402
from codekit import decisions  # noqa: E402
from codekit import secrets as store  # noqa: E402

NL = chr(10)


def run_config(argv, repo):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = kit_config.main(list(argv), repo=str(repo))
        except SystemExit as exc:  # argparse
            code = exc.code
    return code, out.getvalue(), err.getvalue()


class TempRepo(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix="kit-config-")).resolve()
        self.addCleanup(lambda: subprocess.run(["cmd", "/c", "rmdir", "/s", "/q", str(self.work)], check=False)
                        if os.name == "nt" else subprocess.run(["rm", "-rf", str(self.work)], check=False))
        self.repo = self.work / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=str(self.repo), check=True)
        (self.repo / ".agent").mkdir()
        self.env = mock.patch.dict(os.environ, {store.STORE_ENV: "file", "XDG_CONFIG_HOME": str(self.work / "xdg")})
        self.env.start()
        self.addCleanup(self.env.stop)

    def config(self):
        return json.loads((self.repo / ".agent" / "dispatch.config.json").read_text(encoding="utf-8"))


class ConfigCommands(TempRepo):
    def test_init_show_set_unset_validate(self):
        code, out, _ = run_config(["show"], self.repo)
        self.assertEqual(code, 0)
        self.assertIn("不存在，全部缺省", out)
        code, out, _ = run_config(["init"], self.repo)
        self.assertEqual(code, 0, out)
        self.assertEqual(self.config()["allowed_executors"][0]["provider"], "step")
        code, _, err = run_config(["init"], self.repo)
        self.assertEqual((code, "已存在" in err), (1, True))
        code, out, _ = run_config(["set", "decisions.mode", "shadow"], self.repo)
        self.assertEqual(code, 0, out)
        self.assertEqual(self.config()["decisions"], {"mode": "shadow"})
        self.assertIn("_说明", self.config())  # explanation keys survive a write
        code, out, _ = run_config(["set", "kill_grace_seconds", "20"], self.repo)
        self.assertEqual((code, self.config()["kill_grace_seconds"]), (0, 20))
        code, out, _ = run_config(["set", "release_check.allow", '["tests/fixtures/**:home path"]'], self.repo)
        self.assertEqual((code, self.config()["release_check"]), (0, {"allow": ["tests/fixtures/**:home path"]}))
        code, out, _ = run_config(["show", "--json"], self.repo)
        facts = json.loads(out)
        by_key = {row["key"]: row for row in facts["keys"]}
        self.assertEqual((by_key["decisions"]["source"], by_key["planner_paths"]["source"]), ("config", "default"))
        self.assertEqual((facts["decisions"]["mode"], facts["decisions"]["secret"]["source"]), ("shadow", "none"))
        self.assertNotIn("TYPESAFE_API_KEY=", out)
        code, out, _ = run_config(["unset", "decisions.mode"], self.repo)
        self.assertEqual(code, 0, out)
        self.assertNotIn("decisions", self.config())
        code, out, _ = run_config(["validate"], self.repo)
        self.assertEqual((code, "配置有效" in out), (0, True))

    def test_invalid_values_are_refused_without_writing(self):
        run_config(["init"], self.repo)
        before = (self.repo / ".agent" / "dispatch.config.json").read_bytes()
        cases = [["set", "decisions.mode", "maybe"], ["set", "kill_grace_seconds", "0"],
                 ["set", "release_check.allow", '["bad-rule"]'], ["set", "env_keep", '["1bad"]'],
                 ["set", "allowed_executors", '[{"provider": "step"}]'], ["set", "worktree_root", str(self.repo / "inside")],
                 ["set", "extra_protected_paths", '["../x"]']]
        for argv in cases:
            code, _, err = run_config(argv, self.repo)
            self.assertEqual((code, "没有写入" in err), (1, True), (argv, err))
        self.assertEqual((self.repo / ".agent" / "dispatch.config.json").read_bytes(), before)
        code, _, err = run_config(["set", "nonsense", "1"], self.repo)
        self.assertEqual((code, "已知键" in err), (2, True))
        code, _, err = run_config(["unset", "planner_paths"], self.repo)
        self.assertEqual((code, "本来就没有设置" in err), (1, True))

    def test_unknown_keys_in_the_file_fail_validation(self):
        (self.repo / ".agent" / "dispatch.config.json").write_text(json.dumps({"typo_key": 1, "_note": "ok"}), encoding="utf-8")
        code, out, _ = run_config(["validate"], self.repo)
        self.assertEqual(code, 1)
        self.assertIn("未知键 'typo_key'", out)

    def test_decisions_switches_and_marker(self):
        code, out, _ = run_config(["decisions", "shadow"], self.repo)
        self.assertEqual(code, 0, out)
        self.assertIn("实际生效 shadow", out)
        code, out, _ = run_config(["decisions", "marker", "on"], self.repo)
        self.assertTrue((self.repo / ".agent" / decisions.OFF_MARKER).exists())
        code, out, _ = run_config(["decisions", "on"], self.repo)
        self.assertIn("实际生效 off（marker）", out)
        code, out, _ = run_config(["decisions", "marker", "off"], self.repo)
        self.assertFalse((self.repo / ".agent" / decisions.OFF_MARKER).exists())
        code, _, err = run_config(["decisions", "marker"], self.repo)
        self.assertEqual(code, 2)
        code, _, err = run_config(["decisions", "on", "off"], self.repo)
        self.assertEqual(code, 2)

    def test_outside_a_repository_is_a_usage_error(self):
        code, _, err = run_config(["show"], self.work)
        self.assertEqual((code, "不在 Git 仓库" in err), (2, True))


class FileSecrets(TempRepo):
    def test_store_resolve_remove_and_describe(self):
        self.assertEqual(store.source("KIT_TEST_SECRET"), "none")
        with self.assertRaises(store.SecretError):
            store.store("KIT_TEST_SECRET", "short")
        with self.assertRaises(store.SecretError):
            store.store("bad name", "0123456789abcdef")
        self.assertEqual(store.store("KIT_TEST_SECRET", "0123456789abcdef"), "file")
        path = store.secrets_dir() / "KIT_TEST_SECRET"
        self.assertTrue(path.is_file())
        self.assertEqual(store.resolve("KIT_TEST_SECRET"), "0123456789abcdef")
        self.assertEqual(store.source("KIT_TEST_SECRET"), "file")
        with mock.patch.dict(os.environ, {"KIT_TEST_SECRET": "from-env"}):
            self.assertEqual((store.source("KIT_TEST_SECRET"), store.resolve("KIT_TEST_SECRET")), ("env", "from-env"))
        described = store.describe("KIT_TEST_SECRET")
        self.assertEqual((described["source"], described["store_mode"], described["system_backend"]), ("file", "file", None))
        self.assertNotIn("0123456789abcdef", json.dumps(described))
        self.assertEqual(store.remove("KIT_TEST_SECRET"), ["file"])
        self.assertEqual((store.source("KIT_TEST_SECRET"), store.remove("KIT_TEST_SECRET")), ("none", []))

    def test_store_off_reads_only_the_environment(self):
        with mock.patch.dict(os.environ, {store.STORE_ENV: "off"}):
            self.assertEqual(store.backends(), [])
            with self.assertRaises(store.SecretError):
                store.store("KIT_TEST_SECRET", "0123456789abcdef")
            self.assertEqual(store.source("KIT_TEST_SECRET"), "none")

    def test_decisions_resolve_the_stored_key(self):
        store.store("KIT_DECISIONS_KEY", "stored-key-0123456789")
        seen = {}

        def transport(body, headers, timeout, url):
            seen["auth"] = headers.get("Authorization")
            request = json.loads(body)
            answers = {name: {"type": "noul", "noul": 0.5} for name in request["questions"]}
            return json.dumps({"model": "jev-test", "answers": answers, "usage": {"input_tokens": 1}}).encode()
        settings = decisions.settings_from_config({"decisions": {"mode": "on", "api_key_env": "KIT_DECISIONS_KEY"}},
                                                  None, ROOT / "plugins" / "decisions")
        battery = decisions.load_battery(ROOT / "plugins" / "decisions" / "questions" / "mutation-equivalence.json")
        session = decisions.Session(settings, None, transport=transport, environ={})
        self.assertEqual(session.ask(battery, {"x": 1})["status"], "answered")
        self.assertEqual(seen["auth"], "Bearer stored-key-0123456789")
        described = decisions.describe(settings, ROOT / "plugins" / "decisions", environ={})
        self.assertEqual((described["api_key_set"], described["api_key_source"], described["secret_store_mode"]),
                         (False, "file", "file"))


class WindowsBackend(unittest.TestCase):
    def test_round_trip_through_a_fake_advapi32(self):
        import ctypes
        vault = {}

        class FakeApi:
            def CredWriteW(self, cred_ref, flags):
                cred = cred_ref._obj
                blob = ctypes.string_at(cred.CredentialBlob, cred.CredentialBlobSize)
                vault[cred.TargetName] = (cred.Type, cred.UserName, cred.Persist, blob)
                return 1

            def CredReadW(self, target, kind, flags, pointer_ref):
                entry = vault.get(target.value)
                if entry is None:
                    return 0
                cred = store._credential_struct()()
                cred.TargetName = target.value
                cred.Type = entry[0]
                self.keep = ctypes.create_string_buffer(entry[3], len(entry[3]))
                cred.CredentialBlob = ctypes.cast(self.keep, ctypes.POINTER(ctypes.c_char))
                cred.CredentialBlobSize = len(entry[3])
                self.keep_cred = cred
                pointer_ref._obj.value = ctypes.addressof(cred)
                return 1

            def CredFree(self, pointer):
                return None

            def CredDeleteW(self, target, kind, flags):
                return 1 if vault.pop(target.value, None) is not None else 0

        backend = store.WindowsCredentialManager(api=FakeApi())
        self.assertTrue(backend.available())
        self.assertIsNone(backend.read("KIT_FAKE"))
        backend.write("KIT_FAKE", "value-0123456789")
        self.assertEqual(set(vault), {"code-kit:KIT_FAKE"})
        self.assertEqual(vault["code-kit:KIT_FAKE"][:3], (1, "KIT_FAKE", 2))
        self.assertEqual(backend.read("KIT_FAKE"), "value-0123456789")
        self.assertTrue(backend.delete("KIT_FAKE"))
        self.assertFalse(backend.delete("KIT_FAKE"))


class OneTimePage(TempRepo):
    def test_the_page_stores_once_and_refuses_strangers(self):
        urls = []
        result = {}

        def serve():
            result.update(kit_config.run_page("KIT_PAGE_SECRET", timeout=20, open_browser=False, announce=urls.append))
        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        deadline = 50
        while not urls and deadline:
            threading.Event().wait(0.05)
            deadline -= 1
        url = urls[0]
        self.assertTrue(url.startswith("http://127.0.0.1:"))
        base = url.rsplit("/", 1)[0]
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(base + "/wrong-token", timeout=5)
        self.assertEqual(caught.exception.code, 404)
        request = urllib.request.Request(url, headers={"Host": "evil.example"})
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request, timeout=5)
        self.assertEqual(caught.exception.code, 404)
        page = urllib.request.urlopen(url, timeout=5).read().decode("utf-8")
        self.assertIn("KIT_PAGE_SECRET", page)
        self.assertIn('type="password"', page)
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(urllib.request.Request(url, data=b"value=short", method="POST"), timeout=5)
        self.assertEqual(caught.exception.code, 400)
        done = urllib.request.urlopen(urllib.request.Request(url, data=b"value=pasted-secret-0123456789", method="POST"),
                                      timeout=5).read().decode("utf-8")
        self.assertIn("已保存", done)
        thread.join(10)
        self.assertEqual((result["stored"], result["backend"], result["error"]), (True, "file", None))
        self.assertEqual(store.resolve("KIT_PAGE_SECRET"), "pasted-secret-0123456789")

    def test_the_page_times_out_without_a_paste(self):
        result = kit_config.run_page("KIT_PAGE_NONE", timeout=0.3, open_browser=False)
        self.assertEqual((result["stored"], result["error"]), (False, "timeout"))
        self.assertEqual(store.source("KIT_PAGE_NONE"), "none")

    def test_secret_commands_never_print_the_value(self):
        store.store("KIT_CMD_SECRET", "cmd-secret-0123456789")
        code, out, err = run_config(["secret", "check", "KIT_CMD_SECRET"], self.repo)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["source"], "file")
        self.assertNotIn("cmd-secret", out + err)
        with mock.patch.object(kit_config.getpass, "getpass", return_value="typed-secret-0123456789"), \
                mock.patch.object(sys.stdin, "isatty", return_value=True):
            code, out, err = run_config(["secret", "set", "KIT_TTY_SECRET", "--tty"], self.repo)
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out), {"name": "KIT_TTY_SECRET", "stored": True, "backend": "file", "verified": None})
        self.assertNotIn("typed-secret", out + err)
        self.assertEqual(store.resolve("KIT_TTY_SECRET"), "typed-secret-0123456789")
        code, out, _ = run_config(["secret", "remove", "KIT_TTY_SECRET"], self.repo)
        self.assertEqual(json.loads(out)["removed_from"], ["file"])
        code, _, err = run_config(["secret", "check", "bad name"], self.repo)
        self.assertEqual(code, 2)


class PluginsKey(TempRepo):
    """3.0 第一轮 D7：plugins 键只校验格式；非列表值的修复提示先模拟整份校验（C1–C3）。"""

    def write(self, value):
        path = self.repo / ".agent" / "dispatch.config.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def hint_of(self, out):
        marker = "修复："
        self.assertIn(marker, out)
        return out.split(marker, 1)[1].strip().splitlines()[0]

    def test_plugins_section_error_is_the_same_message_without_a_hint(self):
        # 3.0 第一轮：kit_plugins 改配置之前先用它查原配置
        for config in ({}, {"plugins": {}}, {"plugins": {"enabled": ["code-change"], "allowed_permissions": []}}):
            self.assertIsNone(kit_config.plugins_section_error(config), config)
        for config in ({"plugins": None}, {"plugins": []}, {"plugins": {"enabled": None}},
                       {"plugins": {"allowed_permissions": ["x", 5]}}, {"plugins": {"enabled": ["a", "a"]}},
                       {"plugins": {"surprise": []}}):
            message = kit_config.plugins_section_error(config)
            self.assertIsInstance(message, str, config)
            self.assertNotIn("修复：", message)
            self.assertIn(message, kit_config.validate_config(config, kit_config.pd.Repo.discover(str(self.repo)),
                                                              hints=False), config)

    def run_hint(self, hint):
        """把提示里的 `config …` 命令拆成参数再交给 kit_config（提示用单引号包住 JSON 值）。"""
        self.assertTrue(hint.startswith("config "), hint)
        words = hint[len("config "):].split(" ", 2)
        if len(words) == 3 and words[2].startswith("'") and words[2].endswith("'"):
            words[2] = words[2][1:-1]
        return run_config(words, self.repo)

    def test_valid_section_is_shown_and_accepted(self):
        self.write({"plugins": {"enabled": ["decisions"], "allowed_permissions": ["network-decisions"], "_note": "ok"}})
        code, out, _ = run_config(["validate"], self.repo)
        self.assertEqual((code, "配置有效" in out), (0, True), out)
        code, out, _ = run_config(["show", "--json"], self.repo)
        by_key = {row["key"]: row for row in json.loads(out)["keys"]}
        self.assertEqual((code, by_key["plugins"]["source"]), (0, "config"))
        self.write({})
        code, out, _ = run_config(["show", "--json"], self.repo)
        self.assertEqual({row["key"]: row for row in json.loads(out)["keys"]}["plugins"]["source"], "default")

    def test_set_works_and_an_uninstalled_id_is_only_a_format_question(self):
        code, out, _ = run_config(["set", "plugins.enabled", '["decisions", "not-installed-here"]'], self.repo)
        self.assertEqual(code, 0, out)
        self.assertEqual(self.config()["plugins"], {"enabled": ["decisions", "not-installed-here"]})
        code, out, _ = run_config(["set", "plugins.allowed_permissions", '["network-decisions"]'], self.repo)
        self.assertEqual(code, 0, out)
        code, out, _ = run_config(["unset", "plugins.enabled"], self.repo)
        self.assertEqual((code, self.config()["plugins"]), (0, {"allowed_permissions": ["network-decisions"]}))

    def test_format_errors_are_refused_without_a_hint(self):
        cases = [({"enabled": ["Bad"]}, "不是合法的插件 ID"), ({"enabled": ["decisions", "decisions"]}, "重复项"),
                 ({"allowed_permissions": [""]}, "非空字符串"), ({"allowed_permissions": ["a", "a"]}, "重复项"),
                 ({"enabled": [7]}, "不是合法的插件 ID"), ({"surprise": []}, "未知子键")]
        for section, needle in cases:
            self.write({"plugins": section})
            code, out, _ = run_config(["validate"], self.repo)
            self.assertEqual((code, needle in out, "修复：" in out), (1, True, False), (section, out))

    def test_non_list_values_get_a_hint_that_actually_works(self):
        for section, expected in [({"enabled": None}, "config unset plugins.enabled"),
                                  ({"enabled": ["decisions"], "allowed_permissions": None},
                                   "config unset plugins.allowed_permissions"),
                                  ({"enabled": None, "allowed_permissions": None}, "config unset plugins")]:
            self.write({"plugins": section, "kill_grace_seconds": 20})
            code, out, _ = run_config(["validate"], self.repo)
            self.assertEqual(code, 1, out)
            hint = self.hint_of(out)
            self.assertEqual(hint, expected)
            code, out, err = self.run_hint(hint)
            self.assertEqual(code, 0, (section, out, err))
            code, out, _ = run_config(["validate"], self.repo)
            self.assertEqual((code, self.config()["kill_grace_seconds"]), (0, 20), out)
        self.write({"plugins": None})
        code, out, _ = run_config(["validate"], self.repo)
        self.assertEqual((code, self.hint_of(out)), (1, "config unset plugins"))

    def test_no_hint_when_another_key_would_still_block_the_write(self):
        self.write({"plugins": {"enabled": None}, "kill_grace_seconds": 0})
        code, out, _ = run_config(["validate"], self.repo)
        self.assertEqual((code, "修复：" in out), (1, False), out)

    def test_broken_battery_with_decisions_active_gets_the_switch_off_hint(self):
        kit = self.work / "kit"
        shutil.copytree(str(ROOT / "plugins"), str(kit / "plugins"))
        (kit / "plugins" / "decisions" / "questions" / "extra.json").write_text("{}", encoding="utf-8")
        with mock.patch.object(kit_config.pd, "KIT_ROOT", kit), \
                mock.patch.object(kit_config.pd, "DECISIONS_PLUGIN_DIR", kit / "plugins" / "decisions"):
            self.write({"decisions": {"mode": "shadow"}, "plugins": {"enabled": None, "allowed_permissions": None}})
            code, out, _ = run_config(["validate"], self.repo)
            self.assertEqual(code, 1, out)
            hint = self.hint_of(out)
            self.assertTrue(hint.startswith("config set plugins '"), hint)
            replacement = json.loads(hint.split(" ", 3)[3][1:-1])
            installed = sorted(p.name for p in (kit / "plugins").iterdir() if p.is_dir())
            self.assertEqual(replacement, {"enabled": [name for name in installed if name != "decisions"]})
            code, out, err = self.run_hint(hint)
            self.assertEqual(code, 0, (out, err))
            code, out, _ = run_config(["validate"], self.repo)
            self.assertEqual(code, 0, out)
            # 已有合法的 enabled 列表时，替换只去掉 decisions，不把其他插件加进来。
            self.write({"decisions": {"mode": "shadow"},
                        "plugins": {"enabled": ["code-change", "decisions"], "allowed_permissions": None}})
            code, out, _ = run_config(["validate"], self.repo)
            hint = self.hint_of(out)
            self.assertEqual(json.loads(hint.split(" ", 3)[3][1:-1]), {"enabled": ["code-change"]})

    def _kit_with_plugins(self):
        kit = self.work / "kit"
        shutil.copytree(str(ROOT / "plugins"), str(kit / "plugins"))
        return kit

    def test_gate2_a_linked_questions_dir_is_not_read(self):
        # 闸二 B1：决策插件生效时，问题清单经过链接就不读，整份校验报“无效：链接”
        kit = self._kit_with_plugins()
        questions = kit / "plugins" / "decisions" / "questions"
        real = self.work / "real_questions"
        shutil.copytree(str(questions), str(real))
        shutil.rmtree(str(questions))
        if os.name == "nt":
            if subprocess.run(["cmd", "/c", "mklink", "/J", str(questions), str(real)],
                              capture_output=True).returncode != 0:
                self.skipTest("mklink /J 不可用")
        else:
            os.symlink(str(real), str(questions), target_is_directory=True)
        with mock.patch.object(kit_config.pd, "KIT_ROOT", kit), \
                mock.patch.object(kit_config.pd, "DECISIONS_PLUGIN_DIR", kit / "plugins" / "decisions"), \
                mock.patch.object(decisions, "verify_battery_lock", side_effect=AssertionError("不该读题库")):
            self.assertEqual(kit_config.battery_link_problem(), "plugins/decisions/questions")
            errors = kit_config.validate_config({"decisions": {"mode": "shadow"}}, None, hints=False)
            self.assertTrue(any("无效：链接" in error for error in errors), errors)
            self.assertEqual(kit_config.validate_config({}, None, hints=False), [])

    def test_gate2_deeply_nested_config_is_one_error(self):
        # 闸二 B3：嵌套过深的 JSON 是一条 ConfigError，不冒 RecursionError 的堆栈
        (self.repo / ".agent" / "dispatch.config.json").write_text(
            '{"_note": ' + "[" * 5000 + "]" * 5000 + "}", encoding="utf-8")
        code, out, err = run_config(["validate"], self.repo)
        self.assertEqual(code, 1, (out, err))
        self.assertIn("ERROR:", out + err)
        self.assertNotIn("Traceback", out + err)

    def test_gate2_plugin_ids_must_match_in_full(self):
        # 闸二 S2：PLUGIN_ID.match 会放过末尾的换行，配置里的 ID 要整串匹配
        self.assertIsNotNone(kit_config.plugins_section_error({"plugins": {"enabled": ["decisions\n"]}}))
        self.assertIsNone(kit_config.plugins_section_error({"plugins": {"enabled": ["decisions"]}}))

    def test_gate2_fix_hint_has_no_bare_single_quote(self):
        # 闸二 S1：提示整段放进单引号；JSON 里的单引号写成 '，bash 与 PowerShell 都能原样执行
        kit = self._kit_with_plugins()
        (kit / "plugins" / "decisions" / "questions" / "extra.json").write_text("{}", encoding="utf-8")
        with mock.patch.object(kit_config.pd, "KIT_ROOT", kit), \
                mock.patch.object(kit_config.pd, "DECISIONS_PLUGIN_DIR", kit / "plugins" / "decisions"):
            self.write({"decisions": {"mode": "shadow"}, "plugins": {"enabled": None, "_note": "don't"}})
            code, out, _ = run_config(["validate"], self.repo)
            self.assertEqual(code, 1, out)
            hint = self.hint_of(out)
            self.assertTrue(hint.startswith("config set plugins '") and hint.endswith("'"), hint)
            quoted = hint[len("config set plugins '"):-1]
            self.assertNotIn("'", quoted)
            self.assertEqual(json.loads(quoted)["_note"], "don't")
            code, out, err = self.run_hint(hint)
            self.assertEqual(code, 0, (out, err))

    def test_gate2r2_decisions_dir_link_is_found_before_listing_questions(self):
        # 闸二第 2 轮 B1：整个 decisions 目录是 junction 时，先在上级目录查到链接，不跟随它去列 questions/
        kit = self._kit_with_plugins()
        decisions_dir = kit / "plugins" / "decisions"
        real = self.work / "real_decisions"
        shutil.copytree(str(decisions_dir), str(real))
        shutil.rmtree(str(decisions_dir))
        if os.name == "nt":
            if subprocess.run(["cmd", "/c", "mklink", "/J", str(decisions_dir), str(real)],
                              capture_output=True).returncode != 0:
                self.skipTest("mklink /J 不可用")
        else:
            os.symlink(str(real), str(decisions_dir), target_is_directory=True)

        def no_glob(*args, **kwargs):
            raise AssertionError("不该跟随链接去列 questions/")

        with mock.patch.object(kit_config.pd, "KIT_ROOT", kit), \
                mock.patch.object(kit_config.pd, "DECISIONS_PLUGIN_DIR", decisions_dir), \
                mock.patch.object(Path, "glob", no_glob):
            self.assertEqual(kit_config.battery_link_problem(), "plugins/decisions")


class LinkHelpers(unittest.TestCase):
    """3.0 第一轮 D11：pi_dispatch.is_link_or_junction 与 first_link_component（kit_logs、kit_plugins 共用）。"""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="kit-links-")).resolve()
        self.addCleanup(lambda: subprocess.run(["cmd", "/c", "rmdir", "/s", "/q", str(self.root)], check=False)
                        if os.name == "nt" else subprocess.run(["rm", "-rf", str(self.root)], check=False))
        (self.root / "real" / "inner").mkdir(parents=True)
        (self.root / "real" / "inner" / "file.txt").write_text("x", encoding="utf-8")
        (self.root / "outside").mkdir()
        link = self.root / "real" / "linked"
        if os.name == "nt":
            done = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(self.root / "outside")],
                                  capture_output=True, check=False)
            if done.returncode != 0:
                self.skipTest("不能建 junction")
        else:
            os.symlink(str(self.root / "outside"), str(link))

    def test_first_link_component(self):
        pd = kit_config.pd
        self.assertIsNone(pd.first_link_component(self.root, "real/inner/file.txt"))
        self.assertEqual(pd.first_link_component(self.root, "real/linked/anything"), "real/linked")
        self.assertEqual(pd.first_link_component(self.root, "real\\linked"), "real/linked")
        self.assertTrue(pd.is_link_or_junction(self.root / "real" / "linked"))
        self.assertTrue(pd.is_link_or_junction(str(self.root / "real" / "linked")))
        self.assertFalse(pd.is_link_or_junction(self.root / "real" / "inner"))
        self.assertIs(pd._is_link_or_junction, pd.is_link_or_junction)
        for bad in ("../real", "real/../real", "/abs", "C:" + chr(92) + "x", "C:x"):
            with self.assertRaises(ValueError, msg=bad):
                pd.first_link_component(self.root, bad)


if __name__ == "__main__":
    unittest.main()
