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
import socket
import subprocess
import sys
import tempfile
import threading
import time
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


class BatteryLinksAtRuntime(TempRepo):
    """第一轮的残余（用户 2026-10-18 确认另立任务）：调度器运行时加载问题清单、doctor 与 config show 的展示，
    读之前也查链接。经过链接时运行时按 battery_drift 处理（prepare 拒绝，其余命令记一条无意见），展示记 link。"""

    def setUp(self):
        super().setUp()
        self.kit = self.work / "kit"
        shutil.copytree(str(ROOT / "plugins"), str(self.kit / "plugins"))
        self.plugin_dir = self.kit / "plugins" / "decisions"
        questions = self.plugin_dir / "questions"
        real = self.work / "real_questions"
        shutil.copytree(str(questions), str(real))
        shutil.rmtree(str(questions))
        if os.name == "nt":
            if subprocess.run(["cmd", "/c", "mklink", "/J", str(questions), str(real)],
                              capture_output=True).returncode != 0:
                self.skipTest("mklink /J 不可用")
        else:
            os.symlink(str(real), str(questions), target_is_directory=True)
        pd = kit_config.pd
        for patcher in (mock.patch.object(pd, "KIT_ROOT", self.kit),
                        mock.patch.object(pd, "DECISIONS_PLUGIN_DIR", self.plugin_dir),
                        mock.patch.object(decisions, "verify_battery_lock", side_effect=AssertionError("不该读题库")),
                        mock.patch.object(decisions, "load_locked_batteries", side_effect=AssertionError("不该读题库")),
                        mock.patch.object(decisions, "load_batteries", side_effect=AssertionError("不该读题库"))):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.settings_config = {"decisions": {"mode": "shadow"}}

    def test_kit_config_and_the_dispatcher_share_one_check(self):
        self.assertEqual(kit_config.pd.battery_link_problem(), "plugins/decisions/questions")
        self.assertEqual(kit_config.battery_link_problem(), "plugins/decisions/questions")

    def test_prepare_refuses_a_linked_battery(self):
        pd = kit_config.pd
        with self.assertRaises(pd.DispatchError) as caught:
            pd.decisions_session(self.settings_config, self.repo / ".agent", None, strict=True)
        self.assertEqual(caught.exception.code, pd.EXIT_USAGE)
        self.assertIn("经过链接", str(caught.exception))

    def test_other_commands_record_no_opinion(self):
        pd = kit_config.pd
        record = self.work / "decisions.jsonl"
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertIsNone(pd.decisions_session(self.settings_config, self.repo / ".agent", record))
        self.assertIn("battery_drift", out.getvalue())
        rows = [json.loads(line) for line in record.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([(row["status"], row["reason"]) for row in rows], [("no_opinion", "battery_drift")])
        self.assertIn("经过链接", rows[0]["detail"])

    def test_doctor_facts_mark_the_link_without_reading(self):
        pd = kit_config.pd
        settings = decisions.settings_from_config(self.settings_config, self.repo / ".agent", self.plugin_dir)
        described = pd.describe_decisions(decisions, settings)
        self.assertEqual(described["battery_lock"], "link")
        self.assertEqual(described["batteries"], [])
        self.assertEqual(described["plugin_dir"], str(self.plugin_dir))
        self.assertTrue(any("经过链接" in item for item in described["battery_problems"]), described)

    def test_config_show_reports_the_link(self):
        (self.repo / ".agent" / "dispatch.config.json").write_text(json.dumps(self.settings_config), encoding="utf-8")
        code, out, err = run_config(["show", "--json"], self.repo)
        self.assertEqual(code, 1, err)  # 整份校验同样报“无效：链接”
        facts = json.loads(out)
        self.assertEqual(facts["decisions"]["battery_lock"], "link")
        self.assertTrue(any("无效：链接" in error for error in facts["errors"]), facts["errors"])


# ---------------------------------------------------------------------------
# 3.0 第二轮 D7：配置锁、写入事务、历史与审计（设计第 9.2 节 T1–T12）
# ---------------------------------------------------------------------------

#: 子进程驱动：在 publish 里先报告“已持锁”，再等放行文件，用来造出“持锁写入到一半”的交错（不给产品代码加钩子）。
DRIVER = '''
import os, sys, time
sys.path.insert(0, sys.argv[1])
import kit_config
kit_config.LOCK_WAIT_SECONDS = 20.0
barrier = sys.argv[2]
if barrier != "-":
    original = kit_config.ConfigTransaction.publish
    def publish(self, *args, **kwargs):
        open(barrier + ".holding", "w").close()
        deadline = time.time() + 30
        while not os.path.exists(barrier + ".go") and time.time() < deadline:
            time.sleep(0.05)
        return original(self, *args, **kwargs)
    kit_config.ConfigTransaction.publish = publish
sys.exit(kit_config.main(sys.argv[3:]))
'''

IGNORE_RULES = ".agent/runs/\n.agent/dispatch.local.json\n.agent/config-history/\n.agent/audit/\n.agent/.config.lock/\n"


class ConfigTransactions(TempRepo):
    """写入事务：每次写入都有快照、intent、commit；补判、外部改动按资源各算各的；失败的尝试一条记录也不写。"""

    def setUp(self):
        super().setUp()
        (self.repo / ".gitignore").write_text(IGNORE_RULES, encoding="utf-8")
        patcher = mock.patch.object(kit_config, "LOCK_WAIT_SECONDS", 0.5)  # 泄漏的锁要在毫秒级暴露，不是等 30 秒
        patcher.start()
        self.addCleanup(patcher.stop)
        self.agent = self.repo / ".agent"
        self.config_file = self.agent / "dispatch.config.json"

    def records(self, phase=None):
        records, _broken = kit_config.read_audit(kit_config.pd.Repo.discover(str(self.repo)))
        return [r for r in records if phase is None or r["phase"] == phase]

    def audit_bytes(self):
        path = self.agent / "audit" / "management.jsonl"
        return path.read_bytes() if path.exists() else b""

    def set(self, key, value, *extra):
        return run_config(["set", key, value] + list(extra), self.repo)

    def assertNoLock(self):
        self.assertFalse((self.agent / ".config.lock").exists(), "配置锁没有释放")

    # T1 ------------------------------------------------------------------
    def test_each_write_records_snapshot_intent_commit_and_rollback_is_byte_identical(self):
        self.assertEqual(self.set("kill_grace_seconds", "20")[0], 0)
        self.assertEqual(self.set("check_artifact_patterns", '["日志/**"]')[0], 0)  # 非 ASCII 原样写进字节
        intents, commits = self.records("intent"), self.records("commit")
        self.assertEqual([r["action"] for r in intents], ["config.set", "config.set"])
        self.assertEqual([r["result"] for r in commits], ["published", "published"])
        self.assertEqual([r["txn"] for r in commits], [r["txn"] for r in intents])
        first_after = intents[0]["after_ref"]
        snapshot = self.agent / "config-history" / ("%s.json" % first_after["sha256"])
        self.assertTrue(first_after["stored"] and snapshot.is_file())
        self.assertIsNone(intents[0]["before_ref"])  # 文件原来不存在：前态为空
        self.assertEqual(intents[1]["before_ref"]["sha256"], first_after["sha256"])
        second = self.config_file.read_bytes()
        self.assertIn("日志/**".encode("utf-8"), second)
        code, out, err = run_config(["rollback", "1"], self.repo)
        self.assertEqual(code, 0, err)
        self.assertEqual(self.config_file.read_bytes(), snapshot.read_bytes())  # 逐字节回到第 1 条之后
        self.assertEqual(self.records("intent")[-1]["action"], "config.rollback")
        self.assertEqual(run_config(["rollback", "2"], self.repo)[0], 0)
        self.assertEqual(self.config_file.read_bytes(), second)
        self.assertNoLock()

    # T2 ------------------------------------------------------------------
    def test_external_changes_are_observed_once_including_a_checkout_to_old_content(self):
        self.set("kill_grace_seconds", "20")
        a = self.config_file.read_bytes()
        self.set("kill_grace_seconds", "21")
        b = self.config_file.read_bytes()
        self.config_file.write_bytes(a)  # 像 git checkout 回到历史上出现过的内容
        self.set("check_artifact_patterns", '["x"]')
        observed = self.records("observed")
        self.assertEqual(len(observed), 1)
        self.assertEqual(observed[0]["after_ref"]["sha256"], kit_config._sha(a))
        self.assertNotEqual(kit_config._sha(a), kit_config._sha(b))
        self.set("kill_grace_seconds", "22")
        self.assertEqual(len(self.records("observed")), 1)  # 没有新的外部改动

    def test_snapshots_of_suspected_secrets_keep_only_the_hash(self):
        self.set("kill_grace_seconds", "20")
        config = json.loads(self.config_file.read_text(encoding="utf-8"))
        config["_secret_env"] = "opaque_demo_value"  # 说明键也能以 _env 结尾：不在豁免的字段路径里
        self.config_file.write_text(json.dumps(config), encoding="utf-8")
        self.set("kill_grace_seconds", "21")
        observed = self.records("observed")[-1]["after_ref"]
        self.assertFalse(observed["stored"])
        self.assertIn("_secret_env", observed["reason"])
        self.assertFalse((self.agent / "config-history" / ("%s.json" % observed["sha256"])).exists())
        intent = self.records("intent")[-1]
        self.assertFalse(intent["after_ref"]["stored"])  # 新内容也还带着它
        self.assertEqual(kit_config.pd.secret_like_paths({"pricing": {"m": {"source": "sk-" + "a" * 24}}}),
                         ["pricing.m.source"])

    def test_variable_name_fields_are_stored_normally(self):
        self.set("env_remove", '["TYPESAFE_API_KEY"]')
        self.set("decisions", '{"mode": "off", "api_key_env": "TYPESAFE_API_KEY"}')
        for intent in self.records("intent"):
            self.assertTrue(intent["after_ref"]["stored"], intent)
        self.assertEqual(kit_config.pd.secret_like_paths(
            {"decisions": {"api_key_env": "TYPESAFE_API_KEY"}, "env_remove": ["A_KEY"], "env_keep": ["B_TOKEN"],
             "profiles": {"p": {"credential_env": ["STEP_API_KEY"]}}}), [])
        self.assertEqual(kit_config.pd.secret_like_paths({"decisions": {"api_key_env": "not a name"}}),
                         ["decisions.api_key_env"])

    # T3 ------------------------------------------------------------------
    def test_intent_that_cannot_be_written_means_no_replacement(self):
        self.set("kill_grace_seconds", "20")
        before = self.config_file.read_bytes()
        real = kit_config._append_audit

        def failing(repo, record):
            if record["phase"] == "intent":
                raise OSError("disk full")
            real(repo, record)

        with mock.patch.object(kit_config, "_append_audit", failing):
            code, _, err = self.set("kill_grace_seconds", "21")
        self.assertEqual(code, 1)
        self.assertIn("审计写不进去", err)
        self.assertEqual(self.config_file.read_bytes(), before)
        self.assertNoLock()

    # T4 ------------------------------------------------------------------
    def test_interrupted_transactions_are_resolved_once(self):
        self.set("kill_grace_seconds", "20")
        real = kit_config._append_audit

        def no_commit(repo, record):
            if record["phase"] == "commit":
                raise OSError("disk full")
            real(repo, record)

        # ① 替换之后、commit 之前中断：下一次写入补判为 published
        with mock.patch.object(kit_config, "_append_audit", no_commit):
            code, _, err = self.set("kill_grace_seconds", "21")
        self.assertEqual(code, 1)
        self.assertIn("审计记录不全", err)
        self.assertIn('"kill_grace_seconds": 21', self.config_file.read_text(encoding="utf-8"))
        self.set("kill_grace_seconds", "22")
        resolves = self.records("resolve")
        self.assertEqual([r["result"] for r in resolves], ["published"])
        self.assertEqual(self.records("observed"), [])  # 补判为已发布之后，当前内容就是已知的
        # ② 替换之前中断：补判为 aborted
        with mock.patch("os.replace", side_effect=OSError("disk full")):
            self.assertEqual(self.set("kill_grace_seconds", "23")[0], 1)
        self.set("check_artifact_patterns", '["y"]')
        self.assertEqual([r["result"] for r in self.records("resolve")], ["published", "aborted"])
        # ③ 中断之后又被改成既非 before 也非 after 的字节：补判为 unknown，并记一条外部改动
        with mock.patch("os.replace", side_effect=OSError("disk full")):
            self.assertEqual(self.set("kill_grace_seconds", "24")[0], 1)
        config = json.loads(self.config_file.read_text(encoding="utf-8"))
        config["kill_grace_seconds"] = 99
        self.config_file.write_text(json.dumps(config), encoding="utf-8")
        self.set("check_artifact_patterns", '["z"]')
        self.assertEqual([r["result"] for r in self.records("resolve")], ["published", "aborted", "unknown"])
        self.assertEqual(len(self.records("observed")), 1)
        # 判定不再改：之后的写入不再给旧事务写 resolve
        self.set("kill_grace_seconds", "25")
        self.assertEqual(len(self.records("resolve")), 3)

    def test_declared_residual_an_external_revert_to_the_before_bytes_reads_as_aborted(self):
        self.set("kill_grace_seconds", "20")
        before = self.config_file.read_bytes()
        real = kit_config._append_audit

        def no_commit(repo, record):
            if record["phase"] == "commit":
                raise OSError("disk full")
            real(repo, record)

        with mock.patch.object(kit_config, "_append_audit", no_commit):
            self.set("kill_grace_seconds", "21")  # 已替换、commit 缺失
        self.config_file.write_bytes(before)  # 锁外改动恰好改回 before：补判只能判为未发布（D7 写明的残余）
        self.set("check_artifact_patterns", '["x"]')
        self.assertEqual([r["result"] for r in self.records("resolve")], ["aborted"])

    # T5 ------------------------------------------------------------------
    def test_read_modify_write_waits_for_the_lock_and_keeps_both_changes(self):
        driver = self.work / "driver.py"
        driver.write_text(DRIVER, encoding="utf-8")
        barrier = self.work / "barrier"
        child = subprocess.Popen([sys.executable, str(driver), str(ROOT / "scripts"), str(barrier),
                                  "--repo", str(self.repo), "set", "kill_grace_seconds", "21"],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.time() + 30
            while not (self.work / "barrier.holding").exists() and time.time() < deadline:
                time.sleep(0.05)
            self.assertTrue((self.work / "barrier.holding").exists(), "子进程没有拿到锁")
            threading.Timer(1.0, lambda: (self.work / "barrier.go").write_text("go", encoding="utf-8")).start()
            with mock.patch.object(kit_config, "LOCK_WAIT_SECONDS", 20.0):
                code, _, err = self.set("check_artifact_patterns", '["x"]')
            self.assertEqual(code, 0, err)
        finally:
            out, err = child.communicate(timeout=60)
        self.assertEqual(child.returncode, 0, err.decode("utf-8", "replace"))
        config = json.loads(self.config_file.read_text(encoding="utf-8"))
        self.assertEqual((config.get("kill_grace_seconds"), config.get("check_artifact_patterns")), (21, ["x"]))
        self.assertNoLock()

    # T6 ------------------------------------------------------------------
    def test_parallel_writers_keep_every_audit_line_whole(self):
        driver = self.work / "driver.py"
        driver.write_text(DRIVER, encoding="utf-8")
        children = [subprocess.Popen([sys.executable, str(driver), str(ROOT / "scripts"), "-", "--repo", str(self.repo),
                                      "set", key, value], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    for key, value in (("kill_grace_seconds", "30"), ("check_artifact_patterns", '["p"]'),
                                       ("commit_trailers", '["Key: v"]'))]
        for child in children:
            _out, err = child.communicate(timeout=120)
            self.assertEqual(child.returncode, 0, err.decode("utf-8", "replace"))
        records, broken = kit_config.read_audit(kit_config.pd.Repo.discover(str(self.repo)))
        self.assertEqual(broken, [])
        self.assertEqual(sorted(r["phase"] for r in records), ["commit"] * 3 + ["intent"] * 3)
        config = json.loads(self.config_file.read_text(encoding="utf-8"))
        self.assertEqual((config["kill_grace_seconds"], config["check_artifact_patterns"], config["commit_trailers"]),
                         (30, ["p"], ["Key: v"]))

    def test_a_half_line_left_by_a_crash_stays_isolated(self):
        self.set("kill_grace_seconds", "20")
        audit = self.agent / "audit" / "management.jsonl"
        with open(audit, "ab") as handle:
            handle.write(b'{"record_type": "management-audit", "phase": "inte')
        self.set("kill_grace_seconds", "21")
        records, broken = kit_config.read_audit(kit_config.pd.Repo.discover(str(self.repo)))
        self.assertEqual(len(broken), 1)
        self.assertEqual([r["phase"] for r in records], ["intent", "commit", "intent", "commit"])
        code, out, _ = run_config(["history"], self.repo)
        self.assertEqual(code, 0)
        self.assertIn("损坏的记录：第 %d 行" % broken[0], out)

    # T7 ------------------------------------------------------------------
    def test_failed_dry_and_unchanged_attempts_write_nothing(self):
        self.set("kill_grace_seconds", "20")
        with mock.patch("os.replace", side_effect=OSError("disk full")):
            self.set("kill_grace_seconds", "21")  # 留下一条没有终结记录的 intent
        config = json.loads(self.config_file.read_text(encoding="utf-8"))
        config["check_artifact_patterns"] = ["external"]
        # 按字节写 LF：write_text 在 Windows 上会写成 CRLF，那样“没有变化”的写入其实会把 CRLF 改成 LF
        self.config_file.write_bytes((json.dumps(config, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        audit = self.audit_bytes()
        history = {p.name: p.read_bytes() for p in (self.agent / "config-history").iterdir()}
        self.assertEqual(self.set("kill_grace_seconds", '"abc"')[0], 1)  # 校验失败
        self.assertEqual(self.set("kill_grace_seconds", "20")[0], 0)  # 没有变化
        self.assertEqual(self.audit_bytes(), audit)  # 补判与外部改动都没有提前写
        self.assertEqual({p.name: p.read_bytes() for p in (self.agent / "config-history").iterdir()}, history)

    def test_observed_is_not_repeated_when_the_intent_fails_after_it(self):
        self.set("kill_grace_seconds", "20")
        config = json.loads(self.config_file.read_text(encoding="utf-8"))
        config["check_artifact_patterns"] = ["external"]
        self.config_file.write_text(json.dumps(config), encoding="utf-8")
        real = kit_config._append_audit

        def no_intent(repo, record):
            if record["phase"] == "intent":
                raise OSError("disk full")
            real(repo, record)

        with mock.patch.object(kit_config, "_append_audit", no_intent):
            self.assertEqual(self.set("kill_grace_seconds", "21")[0], 1)
        self.set("kill_grace_seconds", "21")
        self.assertEqual(len(self.records("observed")), 1)

    def test_init_and_decisions_record_their_actions(self):
        self.assertEqual(run_config(["init"], self.repo)[0], 0)
        self.assertEqual(run_config(["decisions", "shadow"], self.repo)[0], 0)
        intents = self.records("intent")
        self.assertEqual([(r["action"], r["target"]) for r in intents],
                         [("config.init", None), ("config.decisions", "decisions.mode")])
        self.assertIsNone(intents[0]["before_ref"])

    # T8 ------------------------------------------------------------------
    def test_a_held_lock_is_never_taken_over(self):
        lock = self.agent / ".config.lock"
        for pid, word in ((os.getpid(), "仍在运行"), (self._dead_pid(), "已退出")):
            lock.mkdir()
            (lock / "owner.json").write_text(json.dumps({"pid": pid, "host": socket.gethostname(), "token": "t",
                                                         "created_at": "2000-01-01T00:00:00Z"}), encoding="utf-8")
            old = time.time() - 86400
            os.utime(str(lock), (old, old))  # 很旧的锁也不自动清除
            code, _, err = self.set("kill_grace_seconds", "20")
            self.assertEqual(code, 1)
            self.assertIn("配置锁被占用", err)
            self.assertIn(str(pid), err)
            self.assertIn(word, err)
            self.assertTrue(lock.is_dir())
            shutil.rmtree(str(lock))
        self.assertFalse(self.config_file.exists())

    def _dead_pid(self):
        done = subprocess.run([sys.executable, "-c", "import os; print(os.getpid())"], stdout=subprocess.PIPE)
        return int(done.stdout.decode().strip())

    def test_release_leaves_a_lock_whose_token_is_not_ours(self):
        repo = kit_config.pd.Repo.discover(str(self.repo))
        with kit_config.ConfigLock(repo) as lock:
            (lock.path / "owner.json").write_text(json.dumps({"token": "someone-else"}), encoding="utf-8")
        self.assertTrue((self.agent / ".config.lock").is_dir())

    def test_actor_audit_ids_and_the_unignored_warning(self):
        with mock.patch.dict(os.environ, {"CODEKIT_ACTOR": "agent:planning_review"}):
            self.set("kill_grace_seconds", "20")
        with mock.patch.dict(os.environ, {"CODEKIT_ACTOR": "root"}):
            code, _, err = self.set("kill_grace_seconds", "21")
        self.assertIn("不是 user 或 agent:<角色>", err)
        os.environ.pop("CODEKIT_ACTOR", None)
        self.set("kill_grace_seconds", "22")
        self.assertEqual([r["actor"] for r in self.records("intent")], ["agent:planning_review", "undeclared", "undeclared"])
        ids = [r["audit_id"] for r in self.records()]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertNotIn("没有被 .gitignore 忽略", err)
        (self.repo / ".gitignore").write_text(".agent/runs/\n", encoding="utf-8")
        code, _, err = self.set("kill_grace_seconds", "23")
        self.assertIn(".agent/config-history/ 没有被 .gitignore 忽略", err)

    # T9 ------------------------------------------------------------------
    def test_history_lists_changes_states_and_shows_a_key_diff(self):
        self.set("kill_grace_seconds", "20")
        self.set("decisions", '{"mode": "off"}')
        with mock.patch("os.replace", side_effect=OSError("disk full")):
            self.set("kill_grace_seconds", "21")
        code, out, _ = run_config(["history", "--json"], self.repo)
        self.assertEqual(code, 0)
        rows = json.loads(out)["entries"]
        self.assertEqual([row["number"] for row in rows], [1, 2, 3])
        self.assertEqual(rows[0]["changed_keys"], ["kill_grace_seconds"])
        self.assertEqual(rows[1]["changed_keys"], ["decisions.mode"])
        self.assertEqual([row["state"] for row in rows], ["published", "published", None])  # 只读：不补判
        code, out, _ = run_config(["history"], self.repo)
        self.assertIn("进行中或已中断", out)
        code, out, _ = run_config(["history", "show", "2", "--json"], self.repo)
        self.assertEqual(json.loads(out)["diff"], [{"key": "decisions.mode", "old": None, "new": "off"}])
        self.assertEqual(run_config(["history", "show"], self.repo)[0], 2)
        self.assertEqual(run_config(["rollback", "3"], self.repo)[0], 2)  # 没有发布的不能回滚

    # T10 -----------------------------------------------------------------
    def test_the_two_resources_are_tracked_separately(self):
        repo = kit_config.pd.Repo.discover(str(self.repo))

        def write_local(command):
            with kit_config.config_transaction(repo, "runtime.local_command", "pi", resource="local") as txn:
                txn.publish({"runtimes": {"pi": {"command": command}}})

        self.set("kill_grace_seconds", "20")
        write_local(["pi"])
        self.set("kill_grace_seconds", "21")
        self.assertEqual(self.records("observed"), [])  # 配置 → 本机文件 → 配置：不误报
        real = kit_config._append_audit

        def no_commit(repo_, record):
            if record["phase"] == "commit":
                raise OSError("disk full")
            real(repo_, record)

        with mock.patch.object(kit_config, "_append_audit", no_commit):
            with self.assertRaises(kit_config.AuditIncomplete):
                write_local(["pi", "--x"])
        self.set("kill_grace_seconds", "22")
        self.assertEqual(self.records("resolve"), [])  # 只写配置时不补判本机文件
        write_local(["pi", "--y"])
        resolves = self.records("resolve")
        self.assertEqual([(r["resource"], r["result"]) for r in resolves], [("local", "published")])
        local_intent = self.records("intent")[-1]
        self.assertEqual(local_intent["after_ref"]["kind"], "local-file")
        self.assertFalse(local_intent["after_ref"]["stored"])
        code, out, _ = run_config(["history", "show", str(len(self.records("intent"))), "--json"], self.repo)
        self.assertEqual(json.loads(out)["note"], "本机配置只存哈希")
        self.assertEqual(run_config(["rollback", "2"], self.repo)[0], 2)  # 第 2 条是本机文件的写入

    # 闸二第 1 片的修正 ---------------------------------------------------
    def test_g2s1_b1_history_does_not_diff_against_a_missing_snapshot(self):
        self.set("kill_grace_seconds", "20")
        config = json.loads(self.config_file.read_text(encoding="utf-8"))
        config["_secret_env"] = "opaque_demo_value"  # 之后的快照因疑似凭据只存哈希
        self.config_file.write_bytes((json.dumps(config, indent=2) + "\n").encode("utf-8"))
        self.set("check_artifact_patterns", '["x"]')
        code, out, _ = run_config(["history", "show", "2", "--json"], self.repo)
        self.assertEqual(code, 0)
        shown = json.loads(out)
        self.assertIsNone(shown["diff"])  # 不能当成空配置，报出“kill_grace_seconds: 20 → 未设置”
        self.assertEqual(shown["note"], "疑似凭据，未存内容")
        code, out, _ = run_config(["history", "--json"], self.repo)
        self.assertIsNone(json.loads(out)["entries"][1]["changed_keys"])

    def test_g2s1_s1_publish_new_cleans_up_a_failed_write(self):
        pd = kit_config.pd
        real_fdopen = os.fdopen

        class Failing:
            def __init__(self, fd, mode):
                self.inner = real_fdopen(fd, mode)

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                self.inner.close()
                return False

            def write(self, data):
                raise OSError(28, "No space left on device")

        with mock.patch("os.fdopen", Failing):
            with self.assertRaises(OSError):
                pd.publish_new(self.work / "record.json", b"x")
        self.assertEqual([p.name for p in self.work.iterdir() if p.name.endswith(".tmp")], [])
        self.assertFalse((self.work / "record.json").exists())
        # 闸二第 2 片 S5：os.fdopen 本身失败时由 publish_new 关掉描述符（关不掉，Windows 上临时文件就删不掉）
        with mock.patch("os.fdopen", side_effect=OSError(24, "Too many open files")):
            with self.assertRaises(OSError):
                pd.publish_new(self.work / "record2.json", b"x")
        self.assertEqual([p.name for p in self.work.iterdir() if p.name.endswith(".tmp")], [])

    def test_g2s1_s2_an_interrupted_lock_setup_leaves_no_lock(self):
        for error in (KeyboardInterrupt(), OSError(5, "denied")):
            with self.subTest(error=type(error).__name__):
                with mock.patch.object(kit_config.socket, "gethostname", side_effect=error):
                    code, _, _ = self.set("kill_grace_seconds", "20")
                self.assertEqual(code, 130 if isinstance(error, KeyboardInterrupt) else 1)
                self.assertNoLock()
        self.assertEqual(self.set("kill_grace_seconds", "20")[0], 0)  # 之后照常能写

    def test_g2s1_s3_an_invalid_config_is_refused_even_without_a_change(self):
        self.write_standard({"kill_grace_seconds": "bad"})
        code, _, err = self.set("kill_grace_seconds", '"bad"')
        self.assertEqual(code, 1)
        self.assertIn("没有写入", err)
        self.assertEqual(self.audit_bytes(), b"")

    def test_g2s1_s4_a_structurally_broken_record_is_skipped(self):
        self.set("kill_grace_seconds", "20")
        audit = self.agent / "audit" / "management.jsonl"
        with open(audit, "ab") as handle:
            handle.write(b'{"record_type": "management-audit", "resource": "config", "phase": "commit", '
                         b'"txn": [], "result": "published"}\n')
            handle.write(b'{"record_type": "management-audit", "resource": "config", "phase": "intent", '
                         b'"txn": "t", "action": "config.set", "after_ref": {"sha256": 5}}\n')
            # 闸二第 2 片 S1：资源、阶段是不可哈希的值
            handle.write(b'{"record_type": "management-audit", "phase": "commit", "resource": [], "txn": "t", '
                         b'"result": "published"}\n')
            handle.write(b'{"record_type": "management-audit", "phase": {}, "resource": "config", "txn": "t"}\n')
        code, _, err = self.set("kill_grace_seconds", "21")
        self.assertEqual(code, 0, err)
        records, broken = kit_config.read_audit(kit_config.pd.Repo.discover(str(self.repo)))
        self.assertEqual(len(broken), 4)
        self.assertEqual(run_config(["history"], self.repo)[0], 0)

    def test_g2s1_s5_the_confirmation_hook_sees_the_state_before_the_change(self):
        self.set("kill_grace_seconds", "20")
        seen = []

        def hook(repo, old, new, confirm):
            seen.append((old.get("kill_grace_seconds"), new.get("kill_grace_seconds")))
            return "none"

        with mock.patch.object(kit_config, "_binding_switch_confirmation", hook):
            self.set("kill_grace_seconds", "21")
            run_config(["unset", "kill_grace_seconds"], self.repo)
        self.assertEqual(seen, [(20, 21), (21, None)])

    def write_standard(self, config):
        self.config_file.write_bytes((json.dumps(config, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))

    # T12 -----------------------------------------------------------------
    def test_publish_new_never_overwrites(self):
        pd = kit_config.pd
        target = self.work / "record.json"
        self.assertTrue(pd.publish_new(target, b"one"))
        self.assertFalse(pd.publish_new(target, b"two"))
        self.assertEqual(target.read_bytes(), b"one")
        os.chmod(str(target), 0o444)  # 只读的已存在目标同样是“已存在”
        self.addCleanup(os.chmod, str(target), 0o666)
        self.assertFalse(pd.publish_new(target, b"three"))
        self.assertEqual(target.read_bytes(), b"one")
        with mock.patch("os.open", side_effect=PermissionError(13, "denied")):
            with self.assertRaises(PermissionError):
                pd.publish_new(self.work / "other.json", b"x")
        with mock.patch.object(pd, "IS_WINDOWS", False), \
                mock.patch("os.link", side_effect=OSError(1, "hard links not supported")):
            with self.assertRaises(OSError) as caught:
                pd.publish_new(self.work / "posix.json", b"x")
        self.assertNotIsInstance(caught.exception, FileExistsError)
        self.assertFalse((self.work / "posix.json").exists())
        with mock.patch.object(pd, "IS_WINDOWS", True), \
                mock.patch("os.rename", side_effect=OSError(18, "cross-device link")):
            with self.assertRaises(OSError):
                pd.publish_new(self.work / "xdev.json", b"x")
        self.assertEqual(sorted(p.name for p in self.work.iterdir() if p.name.endswith(".tmp")), [])


class KitInstallKeepsAConfigCreatedMeanwhile(unittest.TestCase):
    """T11：kit_install 检查“配置不存在”之后、写入之前，配置被配置中心建好了：不覆盖它。"""

    def test_install_does_not_overwrite(self):
        import kit_install  # noqa: PLC0415
        work = Path(tempfile.mkdtemp(prefix="kit-config-install-")).resolve()
        self.addCleanup(shutil.rmtree, str(work), True)
        target = work / "target"
        target.mkdir()
        subprocess.run(["git", "init", "-q", str(target)], check=True)
        meanwhile = b'{"kill_grace_seconds": 7}\n'
        real = kit_install.pd.publish_new

        def racing(path, data):
            if path.name == "dispatch.config.json":
                path.write_bytes(meanwhile)  # 配置中心在两步之间建好了配置
            return real(path, data)

        out = io.StringIO()
        with mock.patch.object(kit_install.pd, "publish_new", racing), contextlib.redirect_stdout(out):
            code = kit_install.main(["install", str(target)])
        self.assertEqual(code, 0, out.getvalue())
        self.assertEqual((target / ".agent" / "dispatch.config.json").read_bytes(), meanwhile)
        self.assertIn("KEEP .agent/dispatch.config.json  写入时已存在，未覆盖", out.getvalue())


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
