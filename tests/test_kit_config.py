"""scripts/kit_config.py 与 scripts/codekit/secrets.py 的离线测试（2.7.0）。

没有网络、不碰真实凭据库：凭据后端用文件后端（临时 XDG_CONFIG_HOME）或假的 advapi32；一次性网页用本机
HTTP 客户端访问；决策模型用假传输。配置命令在临时 Git 仓库上跑。
"""
from __future__ import annotations

import contextlib
import io
import json
import os
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


if __name__ == "__main__":
    unittest.main()
