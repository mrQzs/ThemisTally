# -*- coding: utf-8 -*-
"""3.0 第二轮：角色绑定的配置（docs/themis-tally-3.0-r2-角色绑定与配置中心.md D1、D2、D8；测试计划 9.1、9.3 的 M7）。

配置命令在临时 Git 仓库上进程内运行（kit_config.main）；只拷旧文件、没有 kit_roles.py 的布局与 M7b 的交错用子进程。
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
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import kit_config  # noqa: E402
import kit_roles  # noqa: E402
import pi_dispatch as pd  # noqa: E402
from codekit import secrets as store  # noqa: E402

IGNORE_RULES = ".agent/runs/\n.agent/dispatch.local.json\n.agent/config-history/\n.agent/audit/\n.agent/.config.lock/\n"
RUNTIMES = {"pi": {"adapter": "pi"}, "oc": {"adapter": "opencode"}}
PROFILES = {"exec-step": {"runtime": "pi", "model": {"provider": "bb", "id": "step-5-preview"},
                          "options": {"thinking": "high"}},
            "exec-low": {"runtime": "pi", "model": {"provider": "bb", "id": "step-5-mini"},
                         "options": {"thinking": "low"}},
            "oc-x": {"runtime": "oc", "model": {"provider": "oc", "id": "x-1"}}}


def run_config(argv, repo):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = kit_config.main(list(argv), repo=str(repo))
        except SystemExit as exc:  # argparse
            code = exc.code
    return code, out.getvalue(), err.getvalue()


class RolesRepo(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix="kit-roles-")).resolve()
        self.addCleanup(lambda: subprocess.run(["cmd", "/c", "rmdir", "/s", "/q", str(self.work)], check=False)
                        if os.name == "nt" else subprocess.run(["rm", "-rf", str(self.work)], check=False))
        self.repo = self.work / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=str(self.repo), check=True)
        (self.repo / ".agent").mkdir()
        (self.repo / ".gitignore").write_text(IGNORE_RULES, encoding="utf-8")
        for patcher in (mock.patch.dict(os.environ, {store.STORE_ENV: "file", "XDG_CONFIG_HOME": str(self.work / "x")}),
                        mock.patch.object(kit_config, "LOCK_WAIT_SECONDS", 0.5)):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.config_file = self.repo / ".agent" / "dispatch.config.json"

    def write(self, config):
        self.config_file.write_bytes((json.dumps(config, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))

    def base(self, **extra):
        config = {"runtimes": json.loads(json.dumps(RUNTIMES)), "profiles": json.loads(json.dumps(PROFILES))}
        config.update(extra)
        return config

    def errors(self, config):
        return kit_config.validate_config(config, pd.Repo.discover(str(self.repo)))

    def assertRefused(self, key, value, needle):
        before = self.config_file.read_bytes() if self.config_file.exists() else None
        code, _out, err = run_config(["set", key, json.dumps(value, ensure_ascii=False)], self.repo)
        self.assertEqual(code, 1, err)
        self.assertIn("没有写入", err)
        self.assertIn(needle, err)
        self.assertEqual(self.config_file.read_bytes() if self.config_file.exists() else None, before)


class Validation(RolesRepo):
    # C1
    def test_shapes_unknown_keys_and_ids(self):
        self.assertRefused("runtimes", {"pi": {"adapter": "pi", "label": "x"}}, "只接受 adapter")
        self.assertRefused("runtimes", {"Bad_ID": {"adapter": "pi"}}, "ID 不合法")
        self.assertRefused("runtimes", {"pi": {"adapter": "vim"}}, "adapter 必须是")
        self.assertRefused("profiles", [], "profiles 必须是对象")
        self.write(self.base())
        self.assertRefused("profiles.exec-step", {"runtime": "pi", "model": {"provider": "bb", "id": "m"}, "x": 1},
                           "未知键")
        self.assertRefused("roles", {"executor": {"mode": "headless", "profile": "exec-step"}}, "未知角色")

    # C2
    def test_modes_must_fit_the_role(self):
        self.write(self.base())
        self.assertRefused("roles", {"execution": {"mode": "manual"}}, "roles.execution.mode")
        self.assertRefused("roles", {"contract": {"mode": "interactive_host"}}, "roles.contract.mode")
        self.assertRefused("roles", {"planning_review": {"mode": "interactive_host", "host": "opencode"}}, "host 必须是")
        self.assertRefused("roles", {"scheduler_agent": {"mode": "headless", "profile": "exec-step",
                                                          "cadence_seconds": 5}}, "cadence_seconds")
        self.assertEqual(self.errors(self.base(roles={"planning_review": {"mode": "interactive_host", "host": "codex"},
                                                      "contract": {"mode": "manual"},
                                                      "execution": {"mode": "headless", "profile": "exec-step"},
                                                      "scheduler_agent": {"mode": "disabled"}})), [])

    # C3
    def test_references_must_exist(self):
        self.assertRefused("profiles", {"p": {"runtime": "nope", "model": {"provider": "bb", "id": "m"}}}, "没有登记")
        self.write(self.base())
        self.assertRefused("roles", {"execution": {"mode": "headless", "profile": "ghost"}}, "没有登记")
        self.assertRefused("active_preset", "ghost", "不是已有的方案")
        self.assertRefused("presets", {"eco": {"roles": {}}}, "至少写一个角色")

    # C4
    def test_suspected_secrets_are_refused(self):
        self.write(self.base())
        self.assertRefused("presets", {"eco": {"description": "token ghp_" + "a" * 36,
                                               "roles": {"execution": {"mode": "headless", "profile": "exec-step"}}}},
                           "疑似凭据")
        self.assertRefused("profiles.leak", {"runtime": "pi", "model": {"provider": "bb", "id": "sk-" + "b" * 30}},
                           "疑似凭据")
        ok = self.base()
        ok["profiles"]["exec-step"]["credential_env"] = ["STEP_API_KEY"]  # 变量名的字段豁免键名规则
        self.assertEqual(self.errors(ok), [])

    # 闸二第 2 片 B1：拒绝的时候也不回显疑似凭据
    def test_g2s2_b1_refusals_never_echo_secret_values(self):
        self.write(self.base())
        for key, value in (
                ("profiles.leak", {"runtime": "pi", "model": {"provider": "bb", "id": "Bearer abcdefghijklmnop"}}),
                ("profiles.leak", {"runtime": "sk-" + "q" * 30, "model": {"provider": "bb", "id": "m"}}),
                ("roles", {"execution": {"mode": "headless", "profile": "ghp_" + "w" * 36}}),
                ("active_preset", "xoxb-" + "e" * 20)):
            with self.subTest(key=key):
                code, out, err = run_config(["set", key, json.dumps(value)], self.repo)
                self.assertEqual(code, 1, err)
                for fragment in ("abcdefghijklmnop", "q" * 30, "w" * 36, "e" * 20):
                    self.assertNotIn(fragment, out + err)

    # 闸二第 2 片第 2 轮 B1：已有的坏配置在 show 里、旧键的校验错误里，都不显示疑似凭据
    def test_g2s2r2_b1_show_and_old_keys_never_echo_secret_values(self):
        token = "Bearer abcdefghijklmnop"
        config = self.base()
        config["profiles"]["exec-step"]["model"]["id"] = token
        config["allowed_executors"] = [{"provider": "bb", "model": "Bearer zyxwvutsrqponmlk"}]
        self.write(config)
        for argv in (["show"], ["show", "--json"], ["validate"]):
            with self.subTest(argv=argv):
                code, out, err = run_config(argv, self.repo)
                self.assertEqual(code, 1, err)
                self.assertNotIn("abcdefghijklmnop", out + err)
                self.assertNotIn("zyxwvutsrqponmlk", out + err)
        self.config_file.unlink()
        for key, value in (("plugins", "Bearer qwertyuiopasdfgh"), ("plugins.enabled", "Bearer qwertyuiopasdfgh"),
                           ("allowed_executors", [{"provider": "x", "model": "Bearer qwertyuiopasdfgh"}])):
            with self.subTest(key=key):
                code, out, err = run_config(["set", key, json.dumps(value)], self.repo)
                self.assertEqual(code, 1, err)
                self.assertNotIn("qwertyuiopasdfgh", out + err)

    # 闸二第 2 片第 3 轮 B1：config show 的决策摘要不解析含疑似凭据的 decisions
    def test_g2s2r3_b1_decisions_summary_never_shows_secret_values(self):
        self.write({"decisions": {"model": "sk-abcdefghijklmnop"}})  # 能通过模型 ID 的格式检查
        for argv in (["show"], ["show", "--json"]):
            with self.subTest(argv=argv):
                code, out, err = run_config(argv, self.repo)
                self.assertEqual(code, 1, err)
                self.assertNotIn("abcdefghijklmnop", out + err)
                self.assertIn("decisions.model", out + err)
        facts = json.loads(run_config(["show", "--json"], self.repo)[1])
        self.assertEqual(list(facts["decisions"]), ["error"])
        self.assertIn("疑似凭据", facts["decisions"]["error"])

    # 闸二第 2 片第 3 轮 B1：secret set --verify 不把 decisions 里的取值写进结果，也不探测
    def test_g2s2r3_b1_secret_verify_never_shows_secret_values(self):
        self.write({"decisions": {"api_key_env": "ghp_" + "a" * 36}})  # 符合环境变量名的格式

        def probe(_settings):
            raise AssertionError("不应探测")

        tty = mock.Mock()
        tty.isatty.return_value = True
        with mock.patch.object(kit_config.sys, "stdin", tty), \
                mock.patch.object(kit_config.getpass, "getpass", lambda _prompt: "value-for-test"), \
                mock.patch.object(kit_config._decisions, "probe", probe):
            code, out, err = run_config(["secret", "set", "OTHER_KEY", "--tty", "--verify"], self.repo)
        self.assertEqual(code, 0, err)
        self.assertNotIn("a" * 36, out + err)
        result = json.loads(out)
        self.assertIsNone(result["verified"])
        self.assertIn("疑似凭据", result["verify_note"])

    # 闸二第 2 片第 3 轮：键名本身像令牌时同样拒绝；报出的位置、快照、审计与历史里都没有它
    def test_g2s2r3_token_shaped_keys_are_secrets_too(self):
        token = "sk-" + "k" * 24
        fragment = "k" * 24
        profile = {"runtime": "pi", "model": {"provider": "bb", "id": "m"}}
        self.write(self.base())
        code, out, err = run_config(["set", "profiles", json.dumps({token: profile})], self.repo)
        self.assertEqual(code, 1, err)
        self.assertIn(pd.SECRET_KEY_SHOWN, err)
        self.assertNotIn(fragment, out + err)
        self.assertEqual(pd.secret_like_paths({"profiles": {token: {"api_key": "x"}}}),
                         ["profiles.%s" % pd.SECRET_KEY_SHOWN])
        unknown = self.errors({token: 1})  # 顶层的未知键同样不回显
        self.assertEqual(len(unknown), 1)
        self.assertIn(pd.SECRET_KEY_SHOWN, unknown[0])
        self.assertNotIn(fragment, unknown[0])
        self.assertIn("'nope'", self.errors({"nope": 1})[0])
        config = self.base()  # 手改进去的
        config["profiles"][token] = profile
        self.write(config)
        for argv in (["show"], ["show", "--json"], ["validate"]):
            with self.subTest(argv=argv):
                code, out, err = run_config(argv, self.repo)
                self.assertEqual(code, 1, err)
                self.assertNotIn(fragment, out + err)
        code, _out, err = run_config(["unset", "profiles." + token], self.repo)  # 命令行的回显不在 D9 之内
        self.assertEqual(code, 0, err)
        for argv in (["history"], ["history", "--json"], ["history", "show", "1"]):
            with self.subTest(argv=argv):
                code, out, err = run_config(argv, self.repo)
                self.assertEqual(code, 0, err)
                self.assertNotIn(fragment, out + err)
        agent = self.repo / ".agent"
        stored = [path for name in ("audit", "config-history") for path in (agent / name).rglob("*") if path.is_file()]
        self.assertTrue(stored)
        for path in stored:
            self.assertNotIn(fragment.encode("ascii"), path.read_bytes(), path)

    # 闸二第 2 片第 3 轮：doctor 等输出的文本脱敏与共用检查用同一套形状（D9 的“不在此列”一条以此为前提）
    def test_g2s2r3_redaction_covers_every_shape_the_check_flags(self):
        for sample in ("AKIA" + "B" * 16, "AIza" + "c" * 35, "apikey_" + "d" * 30, "xoxs-" + "e" * 12,
                       "sk-" + "f" * 20, "ghp_" + "g" * 36):
            with self.subTest(sample=sample[:6]):
                self.assertTrue(pd.secret_like_paths({"v": sample}))
                self.assertNotIn(sample, pd.redact_secrets("model %s" % sample))
                self.assertNotIn(sample, json.dumps(pd.redact_obj({"model": sample})))

    # 闸二第 2 片第 3 轮之后：内核读 decisions 也先过共用检查；三个命令入口打印的错误都遮令牌形状
    def test_g2s2r3_kernel_decisions_and_error_output_never_show_secret_values(self):
        for section in ({"model": "sk-abcdefghijklmnop"}, {"sk-abcdefghijklmnop": 1}):
            with self.subTest(section=section):
                with self.assertRaises(pd.DispatchError) as caught:
                    pd.decisions_session({"decisions": section}, None, None)
                self.assertIn("疑似凭据", str(caught.exception))
                self.assertNotIn("abcdefghijklmnop", str(caught.exception))
                facts, problems = {}, []
                self.write({"decisions": section})
                pd._doctor_decisions(mock.Mock(repo=str(self.repo), probe_decisions=False), facts, problems, [])
                self.assertEqual(facts["decisions"]["reason"], "config_invalid")
                self.assertNotIn("abcdefghijklmnop", json.dumps([facts, problems], ensure_ascii=False))
        self.assertEqual(pd.redact_tokens("见 AKIA%s 与 sk-%s；task-sk 不动" % ("Q" * 16, "w" * 12)),
                         "见 <redacted> 与 <redacted>；task-sk 不动")
        token = "Bearer zyxwvutsrqponmlk"

        def boom(_args):
            raise pd.DispatchError("替身：%s" % token)

        def boom_config(_args):
            raise kit_config.ConfigError("替身：%s" % token)

        import kit_plugins  # noqa: PLC0415
        for module, name, argv, runner in ((pd, "cmd_status", ["status"], None),
                                           (kit_config, "cmd_validate", ["validate"], run_config),
                                           (kit_plugins, "cmd_list", ["list"], run_plugins)):
            with self.subTest(module=module.__name__):
                with mock.patch.object(module, name, boom if module is not kit_config else boom_config):
                    if runner is None:
                        err = io.StringIO()
                        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                            pd.main(["--repo", str(self.repo)] + argv)
                        err = err.getvalue()
                    else:
                        err = runner(argv, self.repo)[2]
                self.assertIn("替身：<redacted>", err)
                self.assertNotIn("zyxwvutsrqponmlk", err)

    # 闸二第 2 片第 4 轮 B1：内核读配置的唯一入口先过整份的疑似凭据检查，下游拿不到这些取值
    def test_g2s2r4_kernel_refuses_a_config_with_secret_like_values(self):
        token = "sk-" + "t" * 20
        for key, value in (("pricing", {"p/m": {"input": 1, "output": 1, "source": token, "as_of": "2026-10-18"}}),
                           ("commit_trailers", ["Reviewed-By: %s" % token]), ("kill_grace_seconds", token),
                           (token, 1)):
            with self.subTest(key=key[:8]):
                self.write({key: value})
                with self.assertRaises(pd.ConfigSecretError) as caught:
                    pd.Repo(self.repo).config()
                self.assertEqual(caught.exception.code, pd.EXIT_USAGE)
                self.assertNotIn("t" * 20, str(caught.exception))
                out, err = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    code = pd.main(["--repo", str(self.repo), "metrics"])
                self.assertEqual(code, pd.EXIT_USAGE)
                self.assertNotIn("t" * 20, out.getvalue() + err.getvalue())
                self.assertIn("疑似凭据", err.getvalue())

    # 闸二第 2 片第 4 轮 S1：规则变严之前存下的快照，按现在的规则不显示、不回滚，原文件不动
    def test_g2s2r4_snapshots_stored_under_older_rules_are_not_shown(self):
        token = "sk-" + "k" * 24
        self.write(self.base())
        profiles = self.base()["profiles"]
        profiles[token] = {"runtime": "pi", "model": {"provider": "bb", "id": "m"}}
        real = pd.secret_like_paths

        def older(value, path=()):  # 第 3 轮之前：不认令牌形状的键名
            return [found for found in real(value, path) if pd.SECRET_KEY_SHOWN not in found]

        with mock.patch.object(pd, "secret_like_paths", older):
            code, _out, err = run_config(["set", "profiles", json.dumps(profiles)], self.repo)
        self.assertEqual(code, 0, err)
        history = self.repo / ".agent" / "config-history"
        stored = {path.name: path.read_bytes() for path in history.iterdir()}
        self.assertTrue(any(b"k" * 24 in data for data in stored.values()))  # 旧规则下确实存了内容
        for argv in (["history"], ["history", "--json"], ["history", "show", "1"], ["history", "show", "1", "--json"]):
            with self.subTest(argv=argv):
                code, out, err = run_config(argv, self.repo)
                self.assertEqual(code, 0, err)
                self.assertNotIn("k" * 24, out + err)
                self.assertIn("疑似凭据，不显示", out)
        code, out, err = run_config(["rollback", "1"], self.repo)
        self.assertEqual(code, 1, err)
        self.assertIn("疑似凭据，不显示", err)
        self.assertNotIn("k" * 24, out + err)
        self.assertEqual({path.name: path.read_bytes() for path in history.iterdir()}, stored)

    # 闸二第 2 片第 5 轮 S1 的补充：规则变严之前记下的审计 target（例如 set profiles.<令牌形状>）显示时同样不出现
    def test_g2s2r5_audit_targets_recorded_under_older_rules_are_not_shown(self):
        token = "sk-" + "k" * 24
        self.write(self.base())
        code, _out, err = run_config(["set", "profiles.exec-new", json.dumps(
            {"runtime": "pi", "model": {"provider": "bb", "id": "m"}})], self.repo)
        self.assertEqual(code, 0, err)
        audit = kit_config.audit_path(pd.Repo.discover(str(self.repo)))
        original = audit.read_bytes()
        self.assertIn(b'"profiles.exec-new"', original)
        older = original.replace(b'"profiles.exec-new"', ('"profiles.%s"' % token).encode("ascii"))
        audit.write_bytes(older)  # 第 3 轮之前的写法：target 原样记下
        for argv in (["history"], ["history", "--json"], ["history", "show", "1"], ["history", "show", "1", "--json"]):
            with self.subTest(argv=argv):
                code, out, err = run_config(argv, self.repo)
                self.assertEqual(code, 0, err)
                self.assertNotIn("k" * 24, out + err)
        self.assertIn(kit_config.SECRET_SHOWN, run_config(["history"], self.repo)[1])
        self.assertEqual(audit.read_bytes(), older)


    # 闸二总复核 S1：说明键只免形状检查，不免凭据检查——配置中心接受的，内核也读得了
    def test_final_note_keys_are_checked_for_secrets_too(self):
        config = self.base()
        config["_note"] = "sk-" + "n" * 24
        self.write(config)
        code, out, err = run_config(["validate"], self.repo)
        self.assertEqual(code, 1, out + err)
        self.assertIn("疑似凭据", out + err)
        self.assertNotIn("n" * 24, out + err)
        before = self.config_file.read_bytes()
        self.assertEqual(run_config(["set", "kill_grace_seconds", "20"], self.repo)[0], 1)
        self.assertEqual(self.config_file.read_bytes(), before)
        with self.assertRaises(pd.ConfigSecretError):
            pd.Repo(self.repo).config()
        config["_note"] = "普通的说明"
        self.write(config)
        self.assertEqual(run_config(["validate"], self.repo)[0], 0)
        self.assertEqual(pd.Repo(self.repo).config()["_note"], "普通的说明")

    # 闸二总复核 B1：JSON 里像令牌的键名，文本脱敏同样遮掉（与 secret_like_paths 一致）
    def test_final_token_shaped_json_keys_are_redacted(self):
        token = "sk-" + "k" * 24
        self.assertTrue(pd.secret_like_paths({token: "ok"}))
        for text in ('{"%s": "ok"}' % token, 'version {"%s": 1, "%s": 2}' % (token, "ghp_" + "g" * 36)):
            with self.subTest(text=text[:12]):
                shown = pd.redact_secrets(text)
                self.assertNotIn("k" * 24, shown)
                self.assertNotIn("g" * 36, shown)
                self.assertIn("<redacted>", shown)

    # 闸二总复核第 2 轮 B1：说明键的名字本身像令牌时，报错的开头同样不回显它
    def test_final_token_shaped_note_key_is_not_echoed(self):
        key = "_note-sk-" + "n" * 24
        config = self.base()
        config[key] = "普通的说明"
        self.write(config)
        self.assertNotIn("n" * 24, pd.secret_config_error(config, key))
        for argv in (["validate"], ["show"], ["show", "--json"]):
            with self.subTest(argv=argv):
                code, out, err = run_config(argv, self.repo)
                self.assertEqual(code, 1, out + err)
                self.assertIn(pd.SECRET_KEY_SHOWN, out + err)
                self.assertNotIn("n" * 24, out + err)
        with self.assertRaises(pd.ConfigSecretError) as caught:
            pd.Repo(self.repo).config()
        self.assertNotIn("n" * 24, str(caught.exception))

    # 闸二总复核 S2：旧规则下留下的执行模型副本，读回时按现在的规则脱敏
    def test_final_executor_read_back_is_redacted(self):
        run_dir = self.work / "attempt"
        run_dir.mkdir()
        token = "sk-" + "e" * 24
        (run_dir / "contract.json").write_text(json.dumps({"executor": {"role": "execution", "tools": ["read"]}}),
                                               encoding="utf-8")
        meta = {"executor_binding": {"role": "execution", "profile": token, "runtime": "pi", "provider": "bb",
                                     "model": token, "thinking": "high", "record_path": "x"}}
        (run_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
        self.assertNotIn("e" * 24, json.dumps(pd.attempt_executor(run_dir, {})))
        self.assertNotIn("e" * 24, pd.executor_source_text(run_dir, meta))
        (run_dir / "executor.json").write_text(json.dumps({"provider": "bb", "model": token}), encoding="utf-8")
        self.assertNotIn("e" * 24, json.dumps(pd.attempt_executor(run_dir, {})))

    # 闸二第 2 片 S2：引用与枚举字段是 null、数组、对象时，拒绝而不冒堆栈
    def test_g2s2_s2_wrong_types_are_refused_cleanly(self):
        self.write(self.base())
        bad_values = (None, [], {}, 3)
        for value in bad_values:
            with self.subTest(value=value):
                for key, payload in (
                        ("runtimes", {"pi": {"adapter": value}}),
                        ("profiles.p", {"runtime": value, "model": {"provider": "bb", "id": "m"}}),
                        ("roles", {"execution": {"mode": value}}),
                        ("roles", {"planning_review": {"mode": "interactive_host", "host": value}}),
                        ("roles", {"execution": {"mode": "headless", "profile": value}}),
                        ("active_preset", value)):
                    code, _out, err = run_config(["set", key, json.dumps(payload)], self.repo)
                    self.assertEqual(code, 1, (key, payload, err))
                    self.assertNotIn("Traceback", err)
        self.assertEqual(kit_roles.binding_tuple({"roles": {"execution": {"mode": "headless", "profile": []}},
                                                  "profiles": {"p": {"runtime": {}}}}, "execution")[1], None)

    # 闸二第 2 片 S3：说明键与 cadence_seconds
    def test_g2s2_s3_notes_and_explicit_null_cadence(self):
        config = self.base(roles={"scheduler_agent": {"mode": "headless", "profile": "exec-low",
                                                       "cadence_seconds": None}})
        self.assertTrue(any("cadence_seconds" in e for e in self.errors(config)))
        notes = self.base(presets={"_note": "方案说明", "eco": {"roles": {"execution": {
            "mode": "headless", "profile": "exec-step"}}}})
        notes["runtimes"]["_note"] = "本机 CLI 登记"
        notes["profiles"]["_note"] = {"任意": "说明"}
        self.assertEqual(self.errors(notes), [])

    # C5
    def test_runtimes_carry_no_command(self):
        self.assertRefused("runtimes", {"pi": {"adapter": "pi", "command": ["evil.exe"]}}, "dispatch.local.json")

    # C7
    def test_profile_options_by_adapter(self):
        self.write(self.base())
        self.assertRefused("profiles.exec-step", {"runtime": "pi", "model": {"provider": "bb", "id": "m"},
                                                  "options": {"thinking": "turbo"}}, "options.thinking")
        self.assertRefused("profiles.oc-x", {"runtime": "oc", "model": {"provider": "oc", "id": "x"},
                                             "options": {"thinking": "high"}}, "opencode 不接受")
        config = self.base(roles={"execution": {"mode": "headless", "profile": "exec-low"}})
        value, error = kit_roles.resolve_role_executor(config, "execution")
        self.assertIsNone(error)
        self.assertEqual((value["provider"], value["model"], value["thinking"]), ("bb", "step-5-mini", "low"))
        del config["profiles"]["exec-low"]["options"]
        value, _ = kit_roles.resolve_role_executor(config, "execution")
        self.assertEqual(value["thinking"], "high")  # 不写 thinking 时按 high，与合同的缺省相同

    # C8
    def test_credential_env_names(self):
        self.write(self.base())
        self.assertRefused("profiles.exec-step", {"runtime": "pi", "model": {"provider": "bb", "id": "m"},
                                                  "credential_env": ["not a name"]}, "credential_env")

    # C9
    def test_without_v3_keys_show_and_validate_are_unchanged(self):
        code, out, _ = run_config(["show", "--json"], self.repo)
        self.assertEqual(code, 0)
        keys = [row["key"] for row in json.loads(out)["keys"]]
        self.assertEqual(keys[1], "worktree_root")
        self.assertEqual(keys[-5:], list(kit_roles.V3_KEYS))
        self.assertEqual(run_config(["validate"], self.repo)[0], 0)

    def test_resolution_errors_and_codes(self):
        config = self.base()
        _, error = kit_roles.resolve_role_executor(config, "execution")
        self.assertEqual(error["code"], pd.EXIT_USAGE)
        _, error = kit_roles.resolve_role_executor(dict(config, roles={"contract": {"mode": "manual"}}), "contract")
        self.assertIn("manual", error["message"])
        _, error = kit_roles.resolve_role_executor(
            dict(config, roles={"execution": {"mode": "headless", "profile": "oc-x"}}), "execution")
        self.assertEqual(error["code"], pd.EXIT_BLOCKED)  # 未接通的适配器（D6）
        value, error = kit_roles.resolve_role_executor(
            dict(config, roles={"contract": {"mode": "headless", "profile": "exec-step"}},
                 presets={"eco": {"roles": {"contract": {"mode": "headless", "profile": "exec-step"}}}},
                 active_preset="eco"), "contract")
        self.assertIsNone(error)
        self.assertEqual((value["role"], value["runtime"], value["adapter"], value["active_preset"]),
                         ("contract", "pi", "pi", "eco"))


def run_plugins(argv, repo):
    import kit_plugins  # noqa: PLC0415
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = kit_plugins.main(list(argv), repo=str(repo))
        except SystemExit as exc:  # argparse
            code = exc.code
    return code, out.getvalue(), err.getvalue()


class PluginEntries(RolesRepo):
    """闸二第 2 片第 3 轮 B1：plugins 的各个命令先过共用的凭据检查，含疑似凭据就拒绝，不回显、不写入。"""

    def setUp(self):
        super().setUp()
        kit = self.work / "kit"
        shutil.copytree(str(ROOT / "plugins"), str(kit / "plugins"))
        for patcher in (mock.patch.object(pd, "KIT_ROOT", kit),
                        mock.patch.object(pd, "DECISIONS_PLUGIN_DIR", kit / "plugins" / "decisions")):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_g2s2r3_b1_plugin_commands_never_echo_secret_values(self):
        commands = (["list"], ["list", "--json"], ["verify"], ["verify", "--json"], ["show", "decisions"],
                    ["show", "decisions", "--json"], ["enable", "decisions"], ["enable", "decisions", "--dry-run"],
                    ["disable", "decisions"], ["disable", "decisions", "--dry-run"])
        for section in ("Bearer abcdefghijklmnop", {"enabled": ["sk-abcdefghijklmnop"]},
                        {"enabled": ["decisions"], "allowed_permissions": ["sk-abcdefghijklmnop"]}):
            self.write({"plugins": section})
            before = self.config_file.read_bytes()
            for argv in commands:
                with self.subTest(section=section, argv=argv):
                    code, out, err = run_plugins(argv, self.repo)
                    self.assertEqual(code, 1, err)
                    self.assertNotIn("abcdefghijklmnop", out + err)
                    self.assertIn("疑似凭据", err)
                    self.assertEqual(self.config_file.read_bytes(), before)
        self.assertFalse((self.repo / ".agent" / "audit").exists())


class LocalFile(RolesRepo):
    """C6：本机文件 .agent/dispatch.local.json 只接受 runtimes.<id>.command；未登记的 ID 打警告；被跟踪、没被忽略、
    经过链接或有疑似凭据时整份不使用（D3、D9）。"""

    def setUp(self):
        super().setUp()
        self.write(self.base())
        self.local = self.repo / ".agent" / "dispatch.local.json"
        self.target = pd.Repo(self.repo)

    def put(self, data):
        self.local.write_text(json.dumps(data), encoding="utf-8")

    def test_only_runtime_commands_are_accepted(self):
        config = self.base()
        self.assertEqual(kit_roles.read_local(self.target, config), ({}, [], []))
        self.put({"runtimes": {"pi": {"command": ["C:/tools/pi.cmd", "--flag"]}, "_note": "说明"}})
        self.assertEqual(kit_roles.read_local(self.target, config), ({"pi": ["C:/tools/pi.cmd", "--flag"]}, [], []))
        self.assertEqual(kit_roles.local_command(self.target, config, "pi"), (["C:/tools/pi.cmd", "--flag"], []))
        self.assertIsNone(kit_roles.local_command(self.target, config, "oc")[0])
        for bad in ({"runtimes": {"pi": {"command": "pi"}}}, {"runtimes": {"pi": {"command": []}}},
                    {"runtimes": {"pi": {"command": ["pi", ""]}}}, {"runtimes": {"pi": {"command": ["pi"], "env": {}}}},
                    {"runtimes": {"pi": {"adapter": "pi"}}}, {"profiles": {}}, [], {"runtimes": []},
                    {"runtimes": {"Bad_ID": {"command": ["pi"]}}}):
            with self.subTest(bad=bad):
                self.put(bad)
                commands, errors, _warnings = kit_roles.read_local(self.target, config)
                self.assertIsNone(commands)
                self.assertTrue(errors)
                command, lines = kit_roles.local_command(self.target, config, "pi")
                self.assertIsNone(command)
                self.assertTrue(lines and all(line.startswith("ERROR") for line in lines))

    def test_unregistered_runtime_ids_warn(self):
        self.put({"runtimes": {"pi": {"command": ["pi"]}, "ghost": {"command": ["ghost"]}}})
        commands, errors, warnings = kit_roles.read_local(self.target, self.base())
        self.assertEqual((errors, sorted(commands)), ([], ["ghost", "pi"]))
        self.assertEqual(len(warnings), 1)
        self.assertIn("'ghost'", warnings[0])
        command, lines = kit_roles.local_command(self.target, self.base(), "pi")
        self.assertEqual(command, ["pi"])
        self.assertTrue(lines and lines[0].startswith("WARN"))

    def test_tracked_unignored_secret_or_linked_files_are_not_used(self):
        self.put({"runtimes": {"pi": {"command": ["pi"]}}})
        subprocess.run(["git", "add", "-f", ".agent/dispatch.local.json"], cwd=str(self.repo), check=True)
        command, lines = kit_roles.local_command(self.target, self.base(), "pi")
        self.assertIsNone(command)
        self.assertTrue(any(line.startswith("ERROR") and "被 Git 跟踪" in line for line in lines), lines)
        subprocess.run(["git", "rm", "-q", "--cached", ".agent/dispatch.local.json"], cwd=str(self.repo), check=True)
        (self.repo / ".gitignore").write_text(".agent/runs/\n", encoding="utf-8")
        command, lines = kit_roles.local_command(self.target, self.base(), "pi")
        self.assertIsNone(command)
        self.assertTrue(any("没有被 .gitignore 忽略" in line for line in lines), lines)
        (self.repo / ".gitignore").write_text(IGNORE_RULES, encoding="utf-8")
        self.put({"runtimes": {"pi": {"command": ["pi", "--key", "sk-" + "p" * 24]}}})
        command, lines = kit_roles.local_command(self.target, self.base(), "pi")
        self.assertIsNone(command)
        self.assertTrue(any("疑似凭据" in line for line in lines), lines)
        self.assertFalse(any("p" * 24 in line for line in lines))
        self.put({"runtimes": {"pi": {"command": ["pi"]}}})
        agent, moved = self.repo / ".agent", self.work / "agent-elsewhere"
        shutil.move(str(agent), str(moved))
        try:
            if os.name == "nt":
                import _winapi
                _winapi.CreateJunction(str(moved), str(agent))
            else:
                os.symlink(str(moved), str(agent), target_is_directory=True)
        except (OSError, ImportError, AttributeError):
            shutil.move(str(moved), str(agent))
            self.skipTest("建不了目录链接")
        try:
            command, lines = kit_roles.local_command(self.target, self.base(), "pi")
        finally:
            os.rmdir(str(agent)) if os.name == "nt" else os.unlink(str(agent))
            shutil.move(str(moved), str(agent))
        self.assertIsNone(command)
        self.assertTrue(any("经过链接" in line for line in lines), lines)

    def test_a_local_file_that_cannot_be_examined_is_not_treated_as_missing(self):
        """闸二第 3 片 S3：lstat 拒绝访问时报 ERROR、不用它，不当作“没有本机文件”。"""
        self.put({"runtimes": {"pi": {"command": ["pi"]}}})
        blocked = os.path.normcase(str(self.local))
        real = os.lstat

        def lstat(path, *args, **kwargs):
            if os.path.normcase(os.fspath(path)) == blocked:
                raise PermissionError(13, "拒绝访问（替身）", os.fspath(path))
            return real(path, *args, **kwargs)

        with mock.patch.object(os, "lstat", lstat):
            command, lines = kit_roles.local_command(self.target, self.base(), "pi")
        self.assertIsNone(command)
        self.assertTrue(any(line.startswith("ERROR") and "看不了" in line for line in lines), lines)


#: PATH 上的替身（M1–M10）：记下每次调用的参数；pi 交给 tests/stub_pi.py，其余只认 --version。
CLI_STUB = """import json, os, runpy, sys
name, args = sys.argv[1], sys.argv[2:]
log = os.environ.get("CLI_STUB_LOG")
if log:
    with open(log, "a", encoding="utf-8") as handle:
        handle.write(json.dumps([name] + args) + "\\n")
if name == "pi":
    sys.argv = [os.environ["CLI_STUB_PI"]] + args
    try:
        runpy.run_path(os.environ["CLI_STUB_PI"], run_name="__main__")
        code = 0
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 0
    if "--help" in args and os.environ.get("CLI_STUB_HELP_EXIT"):
        code = int(os.environ["CLI_STUB_HELP_EXIT"])
    sys.stdout.flush()
    sys.exit(code)
elif "--version" in args:
    print(os.environ.get("CLI_STUB_VERSION") or "%s 9.9.9" % name)
else:
    sys.exit(3)
"""
#: 提示类调用的标记：出现任何一个就是调用了模型（M9）
PROMPT_MARKERS = ("--mode", "--no-session", "-p", "--print")


class ConfigCenter(RolesRepo):
    """第 4 步：配置中心的命令（设计 4.1、D3、D8、D10；测试计划 9.3 的 M1–M10）。CLI 用 PATH 上的替身。"""

    def setUp(self):
        super().setUp()
        bin_dir = self.work / "bin"
        bin_dir.mkdir()
        stub = self.work / "cli_stub.py"
        stub.write_text(CLI_STUB, encoding="utf-8")
        for program in ("pi", "claude", "codex", "opencode"):
            if os.name == "nt":
                (bin_dir / (program + ".cmd")).write_text(
                    '@"%s" "%s" %s %%*\r\n' % (sys.executable, stub, program), encoding="utf-8")
            else:
                path = bin_dir / program
                path.write_text('#!/bin/sh\nexec "%s" "%s" %s "$@"\n' % (sys.executable, stub, program), encoding="utf-8")
                path.chmod(0o755)
        self.log = self.work / "cli.log"
        env = {"PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", ""), "CLI_STUB_LOG": str(self.log),
               "CLI_STUB_PI": str(ROOT / "tests" / "stub_pi.py"),
               "STUB_MODELS": "bb step-5-preview;bb step-5-mini", "PI_CODING_AGENT_DIR": str(self.work / "pi-agent")}
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        for name in ("PI_DISPATCH_PI_CMD", "STUB_AUTH", "STUB_LIST_FAIL", "STUB_SCENARIO"):
            os.environ.pop(name, None)
        (self.work / "pi-agent").mkdir()

    def calls(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines() if line.strip()]

    def config(self):
        return json.loads(self.config_file.read_text(encoding="utf-8"))

    def assertNoPrompts(self):
        for call in self.calls():
            self.assertFalse(set(call[1:]) & set(PROMPT_MARKERS) or any(arg.startswith("@") for arg in call[1:]), call)

    # M1
    def test_scan_only_asks_for_versions_and_add_registers(self):
        code, out, err = run_config(["runtime", "scan", "--json"], self.repo)
        self.assertEqual(code, 0, err)
        found = {row["adapter"]: row for row in json.loads(out)["found"]}
        self.assertTrue(all(found[adapter]["path"] for adapter in ("pi", "claude-code", "codex", "opencode")), found)
        self.assertEqual(found["codex"]["version"], "codex 9.9.9")
        self.assertTrue(self.calls() and all(call[1:] == ["--version"] for call in self.calls()), self.calls())
        self.assertFalse(self.config_file.exists())
        code, out, err = run_config(["runtime", "scan", "--add"], self.repo)
        self.assertEqual(code, 0, err)
        self.assertEqual(self.config()["runtimes"], {name: {"adapter": name}
                                                     for name in ("pi", "claude-code", "codex", "opencode")})
        self.assertNoPrompts()

    # M2
    def test_runtime_commands_go_to_the_local_file_only(self):
        self.write(self.base())
        command = [str(self.work / "bin" / ("pi.cmd" if os.name == "nt" else "pi")), "--flag"]
        code, out, err = run_config(["runtime", "add", "pi2", "--adapter", "pi", "--command", json.dumps(command)],
                                    self.repo)
        self.assertEqual(code, 0, err)
        self.assertEqual(self.config()["runtimes"]["pi2"], {"adapter": "pi"})  # 提交的配置里没有命令
        local = json.loads((self.repo / ".agent" / "dispatch.local.json").read_text(encoding="utf-8"))
        self.assertEqual(local, {"runtimes": {"pi2": {"command": command}}})
        rows = {row["id"]: row for row in json.loads(run_config(["runtime", "list", "--json"], self.repo)[1])["runtimes"]}
        self.assertEqual((rows["pi2"]["source"], rows["pi"]["source"], rows["oc"]["source"]), ("local", "path", "path"))
        with mock.patch.dict(os.environ, {"PI_DISPATCH_PI_CMD": json.dumps(command)}):  # 环境变量优先于本机文件
            rows = {row["id"]: row for row in json.loads(run_config(["runtime", "list", "--json"], self.repo)[1])["runtimes"]}
        self.assertEqual(rows["pi2"]["source"], "env")
        self.assertEqual(rows["oc"]["source"], "path")  # 只对 pi 适配器
        target = pd.Repo(self.repo)
        self.assertEqual(kit_roles.runtime_command(target, self.config(), "pi2")[:2], (command, "local"))
        # 有引用时拒绝 remove；没有引用时连同本机文件里的命令一起删
        code, _out, err = run_config(["runtime", "remove", "pi"], self.repo)
        self.assertEqual(code, 1, err)
        self.assertIn("被 profile", err)
        code, out, err = run_config(["runtime", "remove", "pi2"], self.repo)
        self.assertEqual(code, 0, err)
        self.assertNotIn("pi2", self.config()["runtimes"])
        self.assertEqual(json.loads((self.repo / ".agent" / "dispatch.local.json").read_text(encoding="utf-8")),
                         {"runtimes": {}})
        # 本机文件被跟踪时，读和写都拒绝
        subprocess.run(["git", "add", "-f", ".agent/dispatch.local.json"], cwd=str(self.repo), check=True)
        before = self.config_file.read_bytes()
        code, _out, err = run_config(["runtime", "add", "pi3", "--adapter", "pi", "--command", json.dumps(command)],
                                     self.repo)
        self.assertEqual(code, 1, err)
        self.assertIn("被 Git 跟踪", err)
        rows = {row["id"]: row for row in json.loads(run_config(["runtime", "list", "--json"], self.repo)[1])["runtimes"]}
        self.assertEqual(rows["pi3"]["source"], "path")  # 已登记，但本机文件不用
        self.assertTrue(any("被 Git 跟踪" in note for note in rows["pi3"]["notes"]))
        self.assertNotEqual(self.config_file.read_bytes(), before)  # 登记本身已写入（两份文件不是一个事务）
        self.assertNoPrompts()

    # M3
    def test_probe_and_models(self):
        self.write(self.base(allowed_executors=[{"provider": "bb", "model": "step-5-preview"}]))
        code, out, err = run_config(["runtime", "probe", "pi", "--json"], self.repo)
        self.assertEqual(code, 0, err)
        probe = json.loads(out)
        self.assertEqual(probe["help"]["missing_flags"], [])
        self.assertEqual([call[0] for call in self.calls()], ["pi", "pi"])
        self.assertTrue(any("--help" in call for call in self.calls()) and any("--version" in call for call in self.calls()))
        self.log.unlink()
        code, out, err = run_config(["runtime", "probe", "oc", "--json"], self.repo)
        self.assertEqual(code, 0, err)
        self.assertEqual(self.calls(), [["opencode", "--version"]])
        code, out, err = run_config(["models", "pi", "--json"], self.repo)
        self.assertEqual(code, 0, err)
        marks = {(row["provider"], row["model"]): row["allowed"] for row in json.loads(out)["models"]}
        self.assertEqual(marks, {("bb", "step-5-preview"): True, ("bb", "step-5-mini"): False})
        code, _out, err = run_config(["models", "oc"], self.repo)
        self.assertEqual(code, 1, err)
        self.assertNoPrompts()

    # M4
    def test_profile_add_edit_remove(self):
        self.write(self.base(roles={"execution": {"mode": "headless", "profile": "exec-step"}}))
        code, _out, err = run_config(["profile", "add", "p1", "--runtime", "pi", "--model", "bb/step-5-mini",
                                      "--thinking", "low", "--credential-env", "STEP_API_KEY"], self.repo)
        self.assertEqual(code, 0, err)
        self.assertEqual(self.config()["profiles"]["p1"], {"runtime": "pi", "model": {"provider": "bb", "id": "step-5-mini"},
                                                           "options": {"thinking": "low"},
                                                           "credential_env": ["STEP_API_KEY"]})
        self.assertEqual(self.calls(), [])  # profile add 不运行任何 CLI（M9）
        code, _out, err = run_config(["profile", "edit", "p1", "--thinking", "high"], self.repo)
        self.assertEqual(code, 0, err)
        self.assertEqual(self.config()["profiles"]["p1"]["options"], {"thinking": "high"})
        self.assertEqual(self.config()["profiles"]["p1"]["model"], {"provider": "bb", "id": "step-5-mini"})
        before = self.config_file.read_bytes()
        code, _out, err = run_config(["profile", "edit", "p1", "--runtime", "oc"], self.repo)  # opencode 不接受 thinking
        self.assertEqual(code, 1, err)
        self.assertEqual(self.config_file.read_bytes(), before)
        code, _out, err = run_config(["profile", "remove", "exec-step"], self.repo)
        self.assertEqual(code, 1, err)
        self.assertIn("roles.execution", err)
        self.assertEqual(run_config(["profile", "remove", "p1"], self.repo)[0], 0)
        self.assertNotIn("p1", self.config()["profiles"])

    # M5
    def test_role_set_modes_warnings_and_unset(self):
        self.write(self.base())
        for argv, expected in ((["contract", "manual"], {"mode": "manual"}),
                               (["planning_review", "interactive_host", "--host", "codex"],
                                {"mode": "interactive_host", "host": "codex"}),
                               (["scheduler_agent", "exec-low", "--cadence-seconds", "120"],
                                {"mode": "headless", "profile": "exec-low", "cadence_seconds": 120}),
                               (["execution", "exec-step"], {"mode": "headless", "profile": "exec-step"})):
            with self.subTest(argv=argv):
                code, out, err = run_config(["role", "set"] + argv, self.repo)
                self.assertEqual(code, 0, err)
                self.assertEqual(self.config()["roles"][argv[0]], expected)
        code, out, err = run_config(["role", "set", "execution", "oc-x"], self.repo)
        self.assertEqual(code, 0, err)
        self.assertIn("WARN", out)
        self.assertIn("没有接通", out)
        code, _out, err = run_config(["role", "set", "execution", "manual"], self.repo)  # execution 只能 headless
        self.assertEqual(code, 1, err)
        self.assertEqual(run_config(["unset", "roles.execution"], self.repo)[0], 0)
        rows = {row["role"]: row for row in json.loads(run_config(["role", "show", "--json"], self.repo)[1])["roles"]}
        self.assertIsNone(rows["execution"]["binding"])
        self.assertIn("由合同决定", run_config(["role", "show"], self.repo)[1])

    # M6
    def test_presets_only_touch_listed_roles(self):
        self.write(self.base(roles={"execution": {"mode": "headless", "profile": "exec-step"},
                                    "contract": {"mode": "manual"}}))
        self.assertEqual(run_config(["preset", "save", "full"], self.repo)[0], 0)
        self.assertEqual(set(self.config()["presets"]["full"]["roles"]), {"execution", "contract"})
        self.assertEqual(run_config(["role", "set", "execution", "exec-low"], self.repo)[0], 0)
        self.assertEqual(run_config(["preset", "save", "eco", "--roles", "execution", "--description", "便宜"],
                                    self.repo)[0], 0)
        self.assertEqual(run_config(["preset", "save", "eco", "--roles", "execution"], self.repo)[0], 1)  # 要 --force
        self.assertEqual(run_config(["role", "set", "contract", "exec-step"], self.repo)[0], 0)
        code, out, err = run_config(["preset", "use", "full"], self.repo)
        self.assertEqual(code, 0, err)
        self.assertIn("运行中与已准备的 attempt 不受影响", out)
        self.assertEqual(self.config()["roles"]["execution"], {"mode": "headless", "profile": "exec-step"})
        self.assertEqual(self.config()["active_preset"], "full")
        code, out, err = run_config(["preset", "use", "eco"], self.repo)
        self.assertEqual(code, 0, err)
        self.assertEqual(self.config()["roles"]["contract"], {"mode": "manual"})  # eco 没列 contract：保持原样
        diff = {row["role"]: row["same"] for row in json.loads(run_config(["preset", "diff", "full", "eco", "--json"],
                                                                        self.repo)[1])["roles"]}
        self.assertEqual(diff, {"contract": False, "execution": False})
        self.assertEqual(run_config(["role", "set", "execution", "exec-step"], self.repo)[0], 0)
        show = json.loads(run_config(["preset", "show", "eco", "--json"], self.repo)[1])
        self.assertTrue(show["active"] and [row["role"] for row in show["roles"] if row["differs"]] == ["execution"])
        rows = {row["role"]: row for row in json.loads(run_config(["role", "show", "--json"], self.repo)[1])["roles"]}
        self.assertTrue(rows["execution"]["differs_from_preset"])
        self.assertEqual(run_config(["preset", "remove", "eco"], self.repo)[0], 1)  # 当前在用
        self.assertEqual(run_config(["preset", "remove", "full"], self.repo)[0], 0)
        self.assertEqual(set(self.config()["presets"]), {"eco"})

    # M8、M9
    def test_doctor_per_role_readiness(self):
        profiles = self.base()["profiles"]
        profiles["exec-step"]["credential_env"] = ["STEP_KEY_SET", "GITHUB_TOKEN", "STEP_KEY_EMPTY", "STEP_KEY_DROPPED"]
        config = self.base(roles={"execution": {"mode": "headless", "profile": "exec-step"},
                                  "contract": {"mode": "headless", "profile": "exec-low"}},
                           env_remove=["STEP_KEY_DROPPED"])
        config["profiles"] = profiles
        self.write(config)
        env = {"STEP_KEY_SET": "x", "GITHUB_TOKEN": "y", "STEP_KEY_EMPTY": "", "STEP_KEY_DROPPED": "z",
               "STUB_MODELS": "bb step-5-preview"}
        with mock.patch.dict(os.environ, env):
            code, out, err = run_config(["doctor", "--json"], self.repo)
        self.assertEqual(code, 1, err)
        rows = {row["role"]: row for row in json.loads(out)["roles"]}
        self.assertEqual(rows["execution"]["credentials"], {"STEP_KEY_SET": True, "GITHUB_TOKEN": False,
                                                            "STEP_KEY_EMPTY": False, "STEP_KEY_DROPPED": False})
        self.assertTrue(rows["execution"]["model_listed"] and rows["execution"]["auth_ready"])
        self.assertFalse(rows["contract"]["model_listed"])  # 共用 runtime 的两个 profile 分别判断
        self.assertNotIn("x", json.dumps(rows["execution"]["credentials"]))
        self.assertEqual(sum(1 for call in self.calls() if call[1:2] == ["--version"]), 1)  # 版本按 runtime 缓存
        with mock.patch.dict(os.environ, {"STEP_KEY_SET": "x", "GITHUB_TOKEN": "y", "STEP_KEY_EMPTY": "e",
                                          "STEP_KEY_DROPPED": "z"}):
            config["env_keep"] = ["GITHUB_TOKEN"]
            config["env_remove"] = []
            config["roles"]["contract"] = {"mode": "manual"}
            self.write(config)
            code, out, err = run_config(["doctor", "--json"], self.repo)
            self.assertEqual(code, 0, out + err)
            with mock.patch.dict(os.environ, {"STUB_AUTH": "missing"}):
                code, out, err = run_config(["doctor"], self.repo)
            self.assertEqual(code, 1, err)
            self.assertIn("凭据未就绪", out)
            config["roles"]["execution"] = {"mode": "headless", "profile": "oc-x"}
            self.write(config)
            code, out, err = run_config(["doctor", "--json"], self.repo)
        self.assertEqual(code, 1, err)
        self.assertTrue(any("没有接通" in problem for row in json.loads(out)["roles"] for problem in row["problems"]))
        self.assertNoPrompts()
        self.assertEqual(run_config(["doctor", "--bogus"], self.repo)[0], 2)

    # M7（第 4 步的命令）：改变生效绑定的写入在运行中同样要 --yes
    def test_new_writers_need_yes_while_attempts_run(self):
        config = self.base(roles={"execution": {"mode": "headless", "profile": "alt-p"}},
                           presets={"eco": {"roles": {"execution": {"mode": "headless", "profile": "exec-low"}}}})
        config["runtimes"]["alt"] = {"adapter": "pi"}  # 不带 options 的 profile：改 adapter 之后仍是合法配置
        config["profiles"]["alt-p"] = {"runtime": "alt", "model": {"provider": "bb", "id": "step-5-preview"}}
        self.write(config)
        run_dir = self.repo / ".agent" / "runs" / "t1" / "attempt-001"
        run_dir.mkdir(parents=True)
        pd.set_state(run_dir, "RUNNING")
        for argv in (["role", "set", "execution", "exec-low"], ["preset", "use", "eco"],
                     ["profile", "edit", "alt-p", "--model", "bb/step-5-mini"],
                     ["runtime", "add", "alt", "--adapter", "opencode", "--force"]):
            with self.subTest(argv=argv[:2]):
                before = self.config_file.read_bytes()
                code, _out, err = run_config(argv, self.repo)
                self.assertEqual(code, 1, err)
                self.assertIn("--yes", err)
                self.assertEqual(self.config_file.read_bytes(), before)
        self.assertEqual(run_config(["role", "set", "execution", "exec-low", "--yes"], self.repo)[0], 0)

    # D9：手改进去的疑似凭据，新命令的显示同样只报位置、不显示取值，也不运行任何 CLI
    def test_new_commands_never_show_secret_values(self):
        config = self.base(roles={"execution": {"mode": "headless", "profile": "exec-step"}},
                           presets={"eco": {"roles": {"execution": {"mode": "headless", "profile": "exec-step"}}}})
        config["profiles"]["exec-step"]["model"]["id"] = "sk-" + "s" * 24
        self.write(config)
        for argv in (["profile", "show"], ["profile", "show", "--json"], ["role", "show"], ["role", "show", "--json"],
                     ["preset", "show", "eco", "--json"], ["preset", "list"], ["preset", "diff", "eco", "eco"],
                     ["runtime", "list", "--json"], ["runtime", "probe", "pi"], ["runtime", "scan"], ["models", "pi"],
                     ["doctor"], ["doctor", "--json"]):
            with self.subTest(argv=argv):  # 读命令先整份校验配置（闸二第 4 片 B1、S3）：不合法就只报错误
                code, out, err = run_config(argv, self.repo)
                self.assertEqual(code, 1, err)
                self.assertIn("疑似凭据", err)
                self.assertNotIn("s" * 24, out + err)
        self.assertEqual(self.calls(), [])  # 拒绝在探测之前

    # 闸二第 4 片 B1：配置里的取值到不了命令参数里——先整份校验，再对完整的 argv 做批处理安全检查
    def test_config_values_never_become_command_arguments(self):
        config = self.base(roles={"execution": {"mode": "headless", "profile": "exec-step"}})
        config["profiles"]["exec-step"]["model"]["id"] = "x&whoami"
        self.write(config)
        code, out, err = run_config(["doctor"], self.repo)
        self.assertEqual(code, 1, err)
        self.assertIn("配置无效", err)
        self.assertNotIn("whoami", out)
        self.assertEqual(self.calls(), [])
        if os.name == "nt":
            wrapper = str(self.work / "bin" / "pi.cmd")
            with self.assertRaises(pd.DispatchError):
                pd.pi_model_readiness([wrapper], "bb", "x&whoami", None, ["high"], None)
            self.assertEqual(self.calls(), [])

    # 闸二第 4 片 S3：合法 JSON 里的坏字段类型不冒堆栈
    def test_bad_shapes_are_reported_not_raised(self):
        config = self.base()
        config["profiles"]["exec-step"]["credential_env"] = None
        self.write(config)
        for argv in (["profile", "show"], ["profile", "show", "--json"], ["doctor"]):
            with self.subTest(argv=argv):
                code, out, err = run_config(argv, self.repo)
                self.assertEqual(code, 1, err)
                self.assertIn("credential_env", err)
                self.assertNotIn("Traceback", err)

    # 闸二第 4 片 B2：外部 CLI 的输出照 doctor 脱敏（键名、结构与令牌形状都算）
    def test_cli_output_is_redacted(self):
        self.write(self.base(roles={"execution": {"mode": "headless", "profile": "oc-x"}}))
        models = ";".join(("bb sk-" + "m" * 24, "Bearer " + "n" * 16, "bb api_key:" + "o" * 16, "bb step-5-preview"))
        with mock.patch.dict(os.environ, {"CLI_STUB_VERSION": '{"api_key": "ordinary-value"}', "STUB_MODELS": models}):
            for argv in (["runtime", "scan"], ["runtime", "scan", "--json"], ["runtime", "probe", "oc"],
                         ["runtime", "probe", "oc", "--json"], ["doctor"], ["doctor", "--json"],
                         ["models", "pi"], ["models", "pi", "--json"]):
                with self.subTest(argv=argv):
                    code, out, err = run_config(argv, self.repo)
                    self.assertNotIn("ordinary-value", out + err)
                    for fragment in ("m" * 24, "n" * 16, "o" * 16):  # 跨列的写法也算（闸二第 4 片第 2 轮 B2）
                        self.assertNotIn(fragment, out + err)
            self.assertIn("step-5-preview", run_config(["models", "pi"], self.repo)[1])

    # 闸二第 4 片 S1：runtime remove 的两步（配置、本机文件）在同一把配置锁里，别的写入插不进中间
    def test_runtime_remove_holds_the_lock_across_both_files(self):
        import threading  # noqa: PLC0415
        config = self.base()
        config["runtimes"]["r"] = {"adapter": "pi"}
        self.write(config)
        local = self.repo / ".agent" / "dispatch.local.json"
        command = [str(self.work / "bin" / ("pi.cmd" if os.name == "nt" else "pi"))]
        local.write_text(json.dumps({"runtimes": {"r": {"command": command}}}), encoding="utf-8")
        paused, go = threading.Event(), threading.Event()
        real = kit_roles.check_local

        def check_local(repo):  # 删配置之后、动本机文件之前停一下
            if threading.current_thread().name == "remover" and not paused.is_set():
                paused.set()
                go.wait(20)
            return real(repo)

        results = {}
        with mock.patch.object(kit_roles, "check_local", check_local):
            remover = threading.Thread(name="remover", target=lambda: results.setdefault(
                "remove", run_config(["runtime", "remove", "r"], self.repo)))
            remover.start()
            self.assertTrue(paused.wait(20))
            results["add"] = run_config(["runtime", "add", "r", "--adapter", "pi", "--command", json.dumps(command)],
                                        self.repo)
            go.set()
            remover.join(30)
        self.assertEqual(results["remove"][0], 0, results["remove"])
        self.assertEqual(results["add"][0], 1, results["add"])  # 等不到配置锁就报错，不插进两步之间
        self.assertNotIn("r", self.config()["runtimes"])
        self.assertNotIn("r", json.loads(local.read_text(encoding="utf-8"))["runtimes"])

    # 闸二第 4 片 S2：doctor 也看 --help 的退出码
    def test_doctor_counts_a_failing_help(self):
        self.write(self.base(roles={"execution": {"mode": "headless", "profile": "exec-step"}}))
        self.assertEqual(run_config(["doctor"], self.repo)[0], 0)
        with mock.patch.dict(os.environ, {"CLI_STUB_HELP_EXIT": "1"}):
            code, out, err = run_config(["doctor"], self.repo)
            self.assertEqual(run_config(["runtime", "probe", "pi"], self.repo)[0], 1)
        self.assertEqual(code, 1, out + err)
        self.assertIn("--help 退出码 1", out)

    # 闸二第 4 片 S4：preset use 同样提示未接通
    def test_preset_use_warns_about_unconnected_bindings(self):
        self.write(self.base(presets={"oc": {"roles": {"execution": {"mode": "headless", "profile": "oc-x"}}}}))
        code, out, err = run_config(["preset", "use", "oc"], self.repo)
        self.assertEqual(code, 0, err)
        self.assertIn("WARN", out)
        self.assertIn("没有接通", out)

    # 闸二第 4 片 S5：doctor 的文本输出在全部就绪时也列出 D10 的各项
    def test_doctor_text_lists_every_item(self):
        profiles = self.base()["profiles"]
        profiles["exec-step"]["credential_env"] = ["STEP_KEY_SET"]
        config = self.base(roles={"execution": {"mode": "headless", "profile": "exec-step"}})
        config["profiles"] = profiles
        self.write(config)
        with mock.patch.dict(os.environ, {"STEP_KEY_SET": "x"}):
            code, out, err = run_config(["doctor"], self.repo)
        self.assertEqual(code, 0, out + err)
        for needle in ("模型 bb/step-5-preview", "thinking high", "模型列表 是", "登录 是", "思考级别 是", "允许列表 不限制",
                       "凭据 STEP_KEY_SET 可用", "已接通"):
            self.assertIn(needle, out)

    # M2 补：本机文件没被忽略、或经过链接时，写也拒绝
    def test_local_file_writes_are_refused_when_unignored_or_linked(self):
        self.write(self.base())
        command = json.dumps([str(self.work / "bin" / ("pi.cmd" if os.name == "nt" else "pi"))])
        (self.repo / ".gitignore").write_text(".agent/runs/\n", encoding="utf-8")
        code, _out, err = run_config(["runtime", "add", "pi", "--adapter", "pi", "--command", command], self.repo)
        self.assertEqual(code, 1, err)
        self.assertIn("没有被 .gitignore 忽略", err)
        self.assertFalse((self.repo / ".agent" / "dispatch.local.json").exists())
        (self.repo / ".gitignore").write_text(IGNORE_RULES, encoding="utf-8")
        agent, moved = self.repo / ".agent", self.work / "agent-elsewhere"
        shutil.move(str(agent), str(moved))
        try:
            if os.name == "nt":
                import _winapi  # noqa: PLC0415
                _winapi.CreateJunction(str(moved), str(agent))
            else:
                os.symlink(str(moved), str(agent), target_is_directory=True)
        except (OSError, ImportError, AttributeError):
            shutil.move(str(moved), str(agent))
            self.skipTest("建不了目录链接")
        try:
            code, _out, err = run_config(["runtime", "add", "pi", "--adapter", "pi", "--command", command], self.repo)
        finally:
            os.rmdir(str(agent)) if os.name == "nt" else os.unlink(str(agent))
            shutil.move(str(moved), str(agent))
        self.assertEqual(code, 1, err)
        self.assertFalse((self.repo / ".agent" / "dispatch.local.json").exists())


    # 闸二总复核 B1：CLI 输出的 JSON 键像令牌时同样遮掉
    def test_final_cli_json_keys_are_redacted(self):
        self.write(self.base(roles={"execution": {"mode": "headless", "profile": "oc-x"}}))
        with mock.patch.dict(os.environ, {"CLI_STUB_VERSION": '{"sk-%s": "ok"}' % ("v" * 24)}):
            for argv in (["runtime", "scan"], ["runtime", "probe", "oc", "--json"], ["doctor", "--json"]):
                with self.subTest(argv=argv):
                    code, out, err = run_config(argv, self.repo)
                    self.assertNotIn("v" * 24, out + err)

    # 闸二总复核 S3：允许列表固定的 thinking，doctor 与 role set 的提示和内核一样判断
    def test_final_pinned_thinking_is_checked_like_the_kernel(self):
        allowed = [{"provider": "bb", "model": "step-5-mini", "thinking": "high"}]
        config = self.base(allowed_executors=allowed)
        self.write(config)
        self.assertEqual(pd.allowed_executor_check(config, "bb", "step-5-mini", "low"), ("thinking", "high"))
        self.assertIsNone(pd.allowed_executor_check(config, "bb", "step-5-mini", "high"))
        self.assertEqual(pd.allowed_executor_check(config, "bb", "x", "high"), ("missing", None))
        code, out, err = run_config(["role", "set", "execution", "exec-low"], self.repo)  # exec-low：step-5-mini、low
        self.assertEqual(code, 0, err)
        self.assertIn("思考级别固定为 high", out)
        code, out, err = run_config(["doctor", "--json"], self.repo)
        self.assertEqual(code, 1, out + err)
        row = {item["role"]: item for item in json.loads(out)["roles"]}["execution"]
        self.assertFalse(row["allowed"])
        self.assertTrue(any("思考级别固定为 high" in problem for problem in row["problems"]))

    # 闸二总复核第 2 轮 S4：已有版本记录的合同按记录核验，命令与 run 的解析顺序相同（本机文件先于 PATH），
    # 记录里的 runtime 不必仍在配置里登记；模型与思考级别取自记录，不看当前绑定
    def test_final_doctor_record_checks_what_run_would_use(self):
        self.write(self.base(roles={"execution": {"mode": "headless", "profile": "exec-low"}}))
        record = {"role": "execution", "profile": "exec-step", "runtime": "pi-old", "adapter": "pi", "provider": "bb",
                  "model": "step-5-preview", "thinking": "high", "contract_json_sha256": "0" * 64,
                  "created_at": "2026-10-18T00:00:00Z", "created_by_attempt": "attempt-001", "active_preset": None,
                  "config_sha256": None}
        path = self.repo / pd.binding_record_rel("demo", 1)
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(record), encoding="utf-8")
        code, out, err = run_config(["doctor", "--record", "demo.v1", "--json"], self.repo)
        self.assertEqual(code, 0, out + err)  # 没有本机文件：与 run 一样用 PATH 上的 pi
        row = json.loads(out)["roles"][0]
        self.assertEqual((row["record"], row["source"], row["model"], row["thinking"], row["model_listed"]),
                         (".agent/runs/demo/binding-v1.json", "path", "step-5-preview", "high", True))
        # 本机文件给 pi-old 指了另一个 pi，它的模型列表里没有 step-5-preview：当前绑定照样就绪，记录不就绪
        old = self.work / "pi_old.py"
        old.write_text('import os, runpy, sys\nos.environ["STUB_MODELS"] = "bb step-5-mini"\n'
                       'sys.argv = [os.environ["CLI_STUB_PI"]] + sys.argv[1:]\n'
                       'runpy.run_path(os.environ["CLI_STUB_PI"], run_name="__main__")\n', encoding="utf-8")
        command = [sys.executable, str(old)]
        (self.repo / ".agent" / "dispatch.local.json").write_text(
            json.dumps({"runtimes": {"pi-old": {"command": command}}}), encoding="utf-8")
        self.assertEqual(run_config(["doctor"], self.repo)[0], 0)
        code, out, err = run_config(["doctor", "--record", "demo.v1", "--json"], self.repo)
        self.assertEqual(code, 1, out + err)
        row = json.loads(out)["roles"][0]
        self.assertEqual((row["source"], row["model_listed"]), ("local", False))
        with contextlib.redirect_stderr(io.StringIO()):  # run 解析出的是同一条命令
            self.assertEqual(pd.resolve_pi_command(pd.Repo(self.repo), "pi-old", self.config()), command)
        code, out, err = run_config(["doctor", "--record", "demo.v1"], self.repo)
        self.assertEqual(code, 1, out + err)
        self.assertIn("版本记录 .agent/runs/demo/binding-v1.json", out)
        # 思考级别同样取自记录
        (self.repo / ".agent" / "dispatch.local.json").unlink()
        path.write_text(json.dumps(dict(record, thinking="turbo")), encoding="utf-8")
        code, out, err = run_config(["doctor", "--record", "demo.v1", "--json"], self.repo)
        self.assertEqual(code, 1, out + err)
        self.assertTrue(any("思考级别 turbo" in problem for problem in json.loads(out)["roles"][0]["problems"]))
        # 写法不对是用法错误；没有记录时说明第一次 prepare 才建立
        self.assertEqual(run_config(["doctor", "--record", "demo"], self.repo)[0], 2)
        code, _out, err = run_config(["doctor", "--record", "demo.v2"], self.repo)
        self.assertEqual(code, 1)
        self.assertIn("还没有版本记录", err)
        self.assertNoPrompts()

    # 闸二总复核第 3 轮 S1：命令里有相对路径时，run（在 worktree 里运行）与这里的探测可能指向不同的文件：报未就绪
    def test_final_doctor_flags_cwd_relative_commands(self):
        self.write(self.base(roles={"execution": {"mode": "headless", "profile": "exec-step"}}))
        (self.work / "pi_rel.py").write_text('import os, runpy, sys\nsys.argv = [os.environ["CLI_STUB_PI"]] + sys.argv[1:]\n'
                                             'runpy.run_path(os.environ["CLI_STUB_PI"], run_name="__main__")\n',
                                             encoding="utf-8")
        local = self.repo / ".agent" / "dispatch.local.json"
        local.write_text(json.dumps({"runtimes": {"pi": {"command": [sys.executable, "pi_rel.py"]}}}), encoding="utf-8")
        here = os.getcwd()
        os.chdir(str(self.work))
        self.addCleanup(os.chdir, here)
        code, out, err = run_config(["doctor", "--json"], self.repo)
        self.assertEqual(code, 1, out + err)
        row = {item["role"]: item for item in json.loads(out)["roles"]}["execution"]
        self.assertEqual(row["source"], "local")
        self.assertTrue(row["model_listed"] and row["auth_ready"])  # 探测本身在这里成功
        self.assertTrue(any("相对路径" in problem and "pi_rel.py" in problem for problem in row["problems"]), row["problems"])
        local.write_text(json.dumps({"runtimes": {"pi": {"command": [sys.executable, str(self.work / "pi_rel.py")]}}}),
                         encoding="utf-8")
        code, out, err = run_config(["doctor"], self.repo)
        self.assertEqual(code, 0, out + err)
        # 第 4 轮 S2：第一项是不带路径分隔符的程序名时按 PATH 找，当前目录下同名的目录不算
        program = os.path.basename(sys.executable)
        (self.work / program).mkdir()
        local.write_text(json.dumps({"runtimes": {"pi": {"command": [program, str(self.work / "pi_rel.py")]}}}),
                         encoding="utf-8")
        with mock.patch.dict(os.environ, {"PATH": os.path.dirname(sys.executable) + os.pathsep + os.environ["PATH"]}):
            code, out, err = run_config(["doctor"], self.repo)
        self.assertEqual(code, 0, out + err)

    # M10：旧 doctor 的共用函数照旧继承环境；config doctor 传 child_env
    def test_shared_readiness_takes_the_environment_explicitly(self):
        seen = []

        def capture(cmd, cwd=None, env=None, timeout=60):
            seen.append(env)
            return 0, "provider model\nbb step-5-preview\n", ""

        with mock.patch.object(pd, "run_capture", capture):
            facts, problems = pd.pi_model_readiness(["pi"], "bb", "step-5-preview", "high", ["high"], None)
            pd.pi_model_readiness(["pi"], "bb", "step-5-preview", "high", ["high"], {"ONLY": "1"})
        self.assertEqual(seen, [None, None, {"ONLY": "1"}, {"ONLY": "1"}])
        self.assertEqual((facts["executor_model_listed"], problems), (True, []))
        self.assertEqual(set(facts), {"executor_model_list", "executor_model_listed", "executor_auth_check"})


class OldLayout(unittest.TestCase):
    """C9：只拷了旧文件、没有 kit_roles.py 的布局里，没有 v3 键的配置命令与插件写入照常可用（D12）。"""

    def test_old_files_only(self):
        work = Path(tempfile.mkdtemp(prefix="kit-roles-old-")).resolve()
        self.addCleanup(shutil.rmtree, str(work), True)
        kit = work / "kit"
        (kit / "scripts").mkdir(parents=True)
        for name in ("pi_dispatch.py", "kit_config.py", "kit_plugins.py"):
            shutil.copy(str(ROOT / "scripts" / name), str(kit / "scripts" / name))
        shutil.copytree(str(ROOT / "scripts" / "codekit"), str(kit / "scripts" / "codekit"))
        shutil.copytree(str(ROOT / "plugins"), str(kit / "plugins"))
        repo = work / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        (repo / ".gitignore").write_text(IGNORE_RULES, encoding="utf-8")
        env = dict(os.environ, PYTHONUTF8="1", CODEKIT_SECRET_STORE="off")

        def tool(*args):
            done = subprocess.run([sys.executable, str(kit / "scripts" / "pi_dispatch.py"), "--repo", str(repo)]
                                  + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, timeout=120)
            return done.returncode, done.stdout.decode("utf-8"), done.stderr.decode("utf-8", "replace")

        for args in (("config", "set", "kill_grace_seconds", "20"), ("config", "decisions", "off"),
                     ("config", "show"), ("config", "validate"), ("plugins", "disable", "code-change"),
                     ("plugins", "enable", "code-change")):
            code, out, err = tool(*args)
            self.assertEqual(code, 0, (args, out, err))
            self.assertNotIn("Traceback", err)
        config = json.loads((repo / ".agent" / "dispatch.config.json").read_text(encoding="utf-8"))
        config["roles"] = {"execution": {"mode": "headless", "profile": "p"}}
        config["runtimes"] = {"pi": {"adapter": "pi"}}
        config["profiles"] = {"p": {"runtime": "pi", "model": {"provider": "bb", "id": "m"}}}
        (repo / ".agent" / "dispatch.config.json").write_text(json.dumps(config), encoding="utf-8")
        code, out, err = tool("config", "validate")
        self.assertEqual(code, 1, (out, err))  # 缺模块经整份校验报出：一行 ERROR，不冒堆栈（D12）
        self.assertEqual([line for line in out.splitlines() if "kit_roles.py" in line and line.startswith("ERROR")],
                         ["ERROR 配置里有角色绑定的键，但 scripts/kit_roles.py 不在本工具旁边"])  # 三个键只报一次
        self.assertNotIn("Traceback", err)


class SwitchConfirmation(RolesRepo):
    """M7：写入改变 execution 或 contract 的生效绑定、而这一刻有在运行的 attempt 时，要 --yes（D8）。"""

    def setUp(self):
        super().setUp()
        self.write(self.base(roles={"execution": {"mode": "headless", "profile": "exec-step"}}))

    def attempt(self, state, claimed=False, name="t1/attempt-001"):
        run_dir = self.repo / ".agent" / "runs" / name
        run_dir.mkdir(parents=True)
        pd.set_state(run_dir, state)
        if claimed:
            (run_dir / "claim").mkdir()
        return run_dir

    def switch(self, *extra):
        return run_config(["set", "roles.execution", json.dumps({"mode": "headless", "profile": "exec-low"})]
                          + list(extra), self.repo)

    def last_confirmation(self):
        records, _ = kit_config.read_audit(pd.Repo.discover(str(self.repo)))
        return [r for r in records if r["phase"] == "intent"][-1]["confirmation"]

    def test_running_attempts_require_yes(self):
        for state, claimed in (("RUNNING", False), ("COLLECTING", False), ("PREPARED", True)):
            with self.subTest(state=state, claimed=claimed):
                run_dir = self.attempt(state, claimed)
                before = self.config_file.read_bytes()
                code, _, err = self.switch()
                self.assertEqual(code, 1, err)
                self.assertIn("t1/attempt-001", err)
                self.assertEqual(self.config_file.read_bytes(), before)
                code, _, err = self.switch("--yes")
                self.assertEqual(code, 0, err)
                self.assertEqual(self.last_confirmation(), "flag")
                shutil.rmtree(str(run_dir))
                self.write(self.base(roles={"execution": {"mode": "headless", "profile": "exec-step"}}))

    def test_finished_or_unclaimed_attempts_do_not(self):
        self.attempt("NEEDS_REVIEW", claimed=True, name="t1/attempt-001")
        self.attempt("PREPARED", claimed=False, name="t2/attempt-001")
        code, _, err = self.switch()
        self.assertEqual(code, 0, err)
        self.assertEqual(self.last_confirmation(), "none")

    def test_writes_that_keep_the_binding_need_no_confirmation(self):
        self.attempt("RUNNING")
        self.assertEqual(run_config(["set", "kill_grace_seconds", "20"], self.repo)[0], 0)
        profiles = self.base()["profiles"]
        profiles["exec-low"]["model"]["id"] = "step-5-other"  # 没有绑定的 profile
        self.assertEqual(run_config(["set", "profiles", json.dumps(profiles)], self.repo)[0], 0)

    def test_every_entry_that_changes_the_binding_is_covered(self):
        self.attempt("RUNNING")
        profiles = self.base()["profiles"]
        profiles["exec-step"]["model"]["id"] = "step-5-other"
        cases = [["set", "profiles", json.dumps(profiles)],
                 ["set", "runtimes", json.dumps({"pi": {"adapter": "opencode"}, "oc": {"adapter": "opencode"}})],
                 ["unset", "roles.execution"]]
        for argv in cases:
            with self.subTest(argv=argv[:2]):
                config = self.base(roles={"execution": {"mode": "headless", "profile": "exec-step"}})
                if argv[1] == "runtimes":  # 改成 opencode 之后，profile 不能再带 pi 才有的 thinking
                    for profile in config["profiles"].values():
                        profile.pop("options", None)
                self.write(config)
                code, _, err = run_config(argv, self.repo)
                self.assertEqual(code, 1, (argv, err))
                self.assertIn("--yes", err)

    def test_g2s2_s4_an_unreadable_runs_directory_is_not_treated_as_idle(self):
        runs = self.repo / ".agent" / "runs"
        (runs / "t1").mkdir(parents=True)
        real = Path.iterdir

        def iterdir(path):
            if path == runs:
                raise PermissionError(13, "拒绝访问（替身）", str(path))
            return real(path)

        with mock.patch.object(Path, "iterdir", iterdir):
            code, _, err = self.switch()
            self.assertEqual(code, 1, err)
            self.assertIn("无法确认有没有在运行的 attempt", err)
            code, _, err = self.switch("--yes")
            self.assertEqual(code, 0, err)
        self.assertEqual(self.last_confirmation(), "flag")

    def test_g2s2r2_s4_an_unreadable_state_is_not_treated_as_idle(self):
        run_dir = self.attempt("RUNNING")
        real = Path.read_bytes

        def read_bytes(path):
            if path == run_dir / "state.json":
                raise PermissionError(13, "拒绝访问（替身）", str(path))
            return real(path)

        with mock.patch.object(Path, "read_bytes", read_bytes), \
                mock.patch.object(pd, "attempt_in_flight", lambda _run_dir: False):  # 吞掉错误的判定也挡不住
            code, _, err = self.switch()
        self.assertEqual(code, 1, err)
        self.assertIn("无法确认有没有在运行的 attempt", err)
        self.assertIn("state.json", err)

    def test_g2s2r3_s4_one_read_decides_both_readability_and_running(self):
        """第一次读成功、之后的读都失败：判定只能用第一次读到的对象（闸二第 2 片第 3 轮 S4）。"""
        run_dir = self.attempt("RUNNING")
        state = run_dir / "state.json"
        reads = []
        real_bytes, real_json = Path.read_bytes, pd.read_json

        def counted(path):
            reads.append(path)
            if len(reads) > 1:
                raise PermissionError(13, "拒绝访问（替身）", str(path))

        def read_bytes(path):
            if path == state:
                counted(path)
            return real_bytes(path)

        def read_json(path):
            if Path(path) == state:
                counted(path)
            return real_json(path)

        with mock.patch.object(Path, "read_bytes", read_bytes), mock.patch.object(pd, "read_json", read_json):
            code, _, err = self.switch()
        self.assertEqual(code, 1, err)
        self.assertIn("有 attempt 在运行", err)
        self.assertIn("t1/attempt-001", err)

    def test_g2s2r3_s4_a_state_that_is_not_an_object_is_not_idle(self):
        run_dir = self.attempt("RUNNING")
        (run_dir / "state.json").write_text(json.dumps(["RUNNING"]), encoding="utf-8")
        code, _, err = self.switch()
        self.assertEqual(code, 1, err)
        self.assertIn("无法确认有没有在运行的 attempt", err)
        self.assertIn("不是对象", err)
        self.assertEqual(self.switch("--yes")[0], 0)
        self.assertEqual(self.last_confirmation(), "flag")

    def test_g2s2r3_s4_entries_that_cannot_be_examined_are_not_idle(self):
        """拒绝访问时 os.path.lexists 返回 False、新版 Path.is_dir 也可能返回 False：扫描在 stat 这一层探测，
        只有“不存在”才算没有。替身让 os.lstat 与 os.stat 对一个位置都报拒绝访问（闸二第 2 片第 3 轮之后）。"""
        run_dir = self.attempt("PREPARED", claimed=True)
        for target in (run_dir / "claim", run_dir / "state.json", run_dir, run_dir.parent):
            with self.subTest(target=target.name):
                blocked = os.path.normcase(str(target))
                real_lstat, real_stat = os.lstat, os.stat

                def guard(real):
                    def call(path, *args, **kwargs):
                        if os.path.normcase(os.fspath(path)) == blocked:
                            raise PermissionError(13, "拒绝访问（替身）", os.fspath(path))
                        return real(path, *args, **kwargs)
                    return call

                with mock.patch.object(os, "lstat", guard(real_lstat)), mock.patch.object(os, "stat", guard(real_stat)):
                    code, _, err = self.switch()
                self.assertEqual(code, 1, err)
                self.assertIn("无法确认有没有在运行的 attempt", err)
                self.assertIn(target.name, err)
        self.assertEqual(run_config(["validate"], self.repo)[0], 0)  # 都没写进去

    def test_rollback_to_a_config_without_bindings(self):
        self.config_file.unlink()
        run_config(["set", "kill_grace_seconds", "20"], self.repo)  # 第 1 条：没有 v3 键
        config = json.loads(self.config_file.read_text(encoding="utf-8"))
        config.update(self.base(roles={"execution": {"mode": "headless", "profile": "exec-step"}}))
        self.assertEqual(run_config(["set", "runtimes", json.dumps(config["runtimes"])], self.repo)[0], 0)
        self.assertEqual(run_config(["set", "profiles", json.dumps(config["profiles"])], self.repo)[0], 0)
        self.assertEqual(run_config(["set", "roles", json.dumps(config["roles"])], self.repo)[0], 0)
        self.attempt("RUNNING")
        code, _, err = run_config(["rollback", "1"], self.repo)
        self.assertEqual(code, 1, err)
        self.assertEqual(run_config(["rollback", "1", "--yes"], self.repo)[0], 0)


#: 子进程驱动（M7b）：在追加 intent 时（确认判定之后、替换之前）报告并等放行文件。
DRIVER = '''
import os, sys, time
sys.path.insert(0, sys.argv[1])
import kit_config
kit_config.LOCK_WAIT_SECONDS = 20.0
barrier = sys.argv[2]
original = kit_config._append_audit
def append(repo, record):
    if record.get("phase") == "intent":
        open(barrier + ".holding", "w").close()
        deadline = time.time() + 30
        while not os.path.exists(barrier + ".go") and time.time() < deadline:
            time.sleep(0.05)
    return original(repo, record)
kit_config._append_audit = append
sys.exit(kit_config.main(sys.argv[3:]))
'''


class SwitchCheckTime(RolesRepo):
    """M7b：判定在检查的那一刻；检查之后、替换之前才领取的 attempt 不纳入这次提醒（D8）。"""

    def test_attempt_claimed_after_the_check_is_not_part_of_this_reminder(self):
        self.write(self.base(roles={"execution": {"mode": "headless", "profile": "exec-step"}}))
        driver = self.work / "driver.py"
        driver.write_text(DRIVER, encoding="utf-8")
        barrier = self.work / "barrier"
        child = subprocess.Popen([sys.executable, str(driver), str(ROOT / "scripts"), str(barrier), "--repo",
                                  str(self.repo), "set", "roles.execution",
                                  json.dumps({"mode": "headless", "profile": "exec-low"})],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.time() + 30
            while not (self.work / "barrier.holding").exists() and time.time() < deadline:
                time.sleep(0.05)
            self.assertTrue((self.work / "barrier.holding").exists())
            run_dir = self.repo / ".agent" / "runs" / "t1" / "attempt-001"
            run_dir.mkdir(parents=True)
            pd.set_state(run_dir, "RUNNING")  # 检查之后才领取
            (self.work / "barrier.go").write_text("go", encoding="utf-8")
        finally:
            _out, err = child.communicate(timeout=60)
        self.assertEqual(child.returncode, 0, err.decode("utf-8", "replace"))
        records, _ = kit_config.read_audit(pd.Repo.discover(str(self.repo)))
        self.assertEqual([r for r in records if r["phase"] == "intent"][-1]["confirmation"], "none")


if __name__ == "__main__":
    unittest.main()
